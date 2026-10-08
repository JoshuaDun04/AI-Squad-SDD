/**
 * Uma sessão Baileys por restaurante. Credenciais em DATA_DIR/sessoes/<restaurante_id>
 * (volume persistente). Repassa mensagens e mudanças de conexão para a API.
 */

import { mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";

import makeWASocket, {
  Browsers,
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
  type WASocket,
} from "baileys";
import pino from "pino";
import QRCode from "qrcode";

import type { ClienteApi } from "./api.js";
import { SessaoIndisponivel, type Sessoes } from "./app.js";
import { MapaContatos } from "./contatos.js";
import { mascarar, normalizar, type MensagemBaileys } from "./normalizar.js";

const MAX_RECONEXOES = 5;

interface Estado {
  socket: WASocket | null;
  conectado: boolean;
  encerrando: boolean;
  reconexoes: number;
  /** contatos que só chegam como LID, persistidos em DATA_DIR/contatos */
  contatos: MapaContatos;
}

export class SessoesBaileys implements Sessoes {
  private readonly estados = new Map<string, Estado>();
  private readonly logger = pino({ level: process.env.BAILEYS_LOG ?? "warn" });

  constructor(
    private readonly dataDir: string,
    private readonly api: ClienteApi,
  ) {}

  private pasta(restauranteId: string): string {
    return path.join(this.dataDir, "sessoes", restauranteId);
  }

  /** Ao subir, reabre as sessões que já têm credenciais salvas. */
  async restaurar(): Promise<void> {
    const raiz = path.join(this.dataDir, "sessoes");
    await mkdir(raiz, { recursive: true });
    for (const id of await readdir(raiz)) {
      await this.iniciar(id).catch((e) => console.error(`falha ao restaurar sessão ${id}: ${(e as Error).name}`));
    }
  }

  async iniciar(restauranteId: string): Promise<void> {
    const atual = this.estados.get(restauranteId);
    if (atual?.socket && !atual.encerrando) {
      if (atual.conectado) {
        await this.api.enviarEvento({ tipo: "status_conexao", restaurante_id: restauranteId, status: "conectado" });
      }
      return; // já está aberta (ou aguardando QR)
    }
    const estado: Estado = atual ?? {
      socket: null,
      conectado: false,
      encerrando: false,
      reconexoes: 0,
      contatos: await MapaContatos.abrir(this.dataDir, restauranteId),
    };
    estado.encerrando = false;
    this.estados.set(restauranteId, estado);
    await this.abrir(restauranteId, estado);
  }

  private async abrir(restauranteId: string, estado: Estado): Promise<void> {
    const pasta = this.pasta(restauranteId);
    await mkdir(pasta, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(pasta);
    let version: [number, number, number] | undefined;
    try {
      version = (await fetchLatestBaileysVersion()).version;
    } catch {
      version = undefined; // usa a versão embutida na biblioteca
    }
    const socket = makeWASocket({
      auth: state,
      version,
      browser: Browsers.ubuntu("PDV Restaurantes"),
      logger: this.logger,
      markOnlineOnConnect: false,
      syncFullHistory: false,
    });
    estado.socket = socket;

    socket.ev.on("creds.update", saveCreds);

    socket.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
      if (qr) {
        const dataUrl = await QRCode.toDataURL(qr, { margin: 1, width: 320 });
        await this.api.enviarEvento({
          tipo: "status_conexao",
          restaurante_id: restauranteId,
          status: "aguardando_qr",
          qr_code: dataUrl,
        });
      }
      if (connection === "open") {
        estado.conectado = true;
        estado.reconexoes = 0;
        console.info(`sessão conectada restaurante=${restauranteId}`);
        await this.api.enviarEvento({ tipo: "status_conexao", restaurante_id: restauranteId, status: "conectado" });
      }
      if (connection === "close") {
        estado.conectado = false;
        estado.socket = null;
        const codigo = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)?.output?.statusCode;
        const deslogado = codigo === DisconnectReason.loggedOut;
        if (estado.encerrando || deslogado || estado.reconexoes >= MAX_RECONEXOES) {
          if (deslogado) {
            await rm(pasta, { recursive: true, force: true });
            await estado.contatos.apagar();
          }
          this.estados.delete(restauranteId);
          console.info(`sessão encerrada restaurante=${restauranteId} codigo=${codigo ?? "?"}`);
          await this.api.enviarEvento({ tipo: "status_conexao", restaurante_id: restauranteId, status: "desconectado" });
          return;
        }
        estado.reconexoes += 1;
        const espera = Math.min(30_000, 1000 * 2 ** estado.reconexoes);
        console.warn(`sessão caiu restaurante=${restauranteId} codigo=${codigo ?? "?"}; reconectando em ${espera} ms`);
        setTimeout(() => {
          this.abrir(restauranteId, estado).catch((e) =>
            console.error(`falha ao reconectar restaurante=${restauranteId}: ${(e as Error).name}`),
          );
        }, espera);
      }
    });

    socket.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") return;
      for (const bruta of messages) {
        const msg = normalizar(bruta as unknown as MensagemBaileys);
        if (!msg) continue;
        await estado.contatos.lembrar(msg.telefone, msg.jidResposta);
        const ok = await this.api.enviarEvento({
          tipo: "mensagem",
          restaurante_id: restauranteId,
          mensagem_id: msg.mensagemId,
          telefone: msg.telefone,
          nome_perfil: msg.nomePerfil,
          texto: msg.texto,
          recebida_em: new Date().toISOString(),
        });
        if (!ok) console.error(`mensagem não entregue à API cliente=${mascarar(msg.telefone)}`);
      }
    });
  }

  async encerrar(restauranteId: string): Promise<void> {
    const estado = this.estados.get(restauranteId);
    if (estado?.socket) {
      estado.encerrando = true;
      try {
        await estado.socket.logout();
      } catch {
        estado.socket.end(undefined);
      }
    }
    this.estados.delete(restauranteId);
    await rm(this.pasta(restauranteId), { recursive: true, force: true });
    await (estado?.contatos ?? (await MapaContatos.abrir(this.dataDir, restauranteId))).apagar();
  }

  async enviar(restauranteId: string, telefone: string, texto: string): Promise<void> {
    const estado = this.estados.get(restauranteId);
    if (!estado?.socket || !estado.conectado) throw new SessaoIndisponivel();
    const jid = estado.contatos.jid(telefone);
    await estado.socket.sendMessage(jid, { text: texto });
  }
}
