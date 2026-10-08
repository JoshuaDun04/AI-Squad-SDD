/**
 * Endereços de resposta dos contatos que chegam só com identificador LID
 * (o WhatsApp esconde o número). Persistido por restaurante para que os avisos
 * de status continuem chegando depois de reiniciar o gateway.
 *
 * Só guarda o necessário para responder (RN-10): o par identificador → JID LID.
 * Contatos com número normal não são gravados, porque o JID sai do próprio número.
 */

import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";

export class MapaContatos {
  private readonly mapa = new Map<string, string>();
  private gravacao: Promise<void> = Promise.resolve();

  private constructor(private readonly arquivo: string) {}

  static async abrir(dataDir: string, restauranteId: string): Promise<MapaContatos> {
    const arquivo = path.join(dataDir, "contatos", `${restauranteId}.json`);
    const m = new MapaContatos(arquivo);
    try {
      const dados = JSON.parse(await readFile(arquivo, "utf8")) as Record<string, unknown>;
      for (const [chave, jid] of Object.entries(dados)) {
        if (/^\d{8,15}$/.test(chave) && typeof jid === "string" && jid.endsWith("@lid")) m.mapa.set(chave, jid);
      }
    } catch {
      /* arquivo inexistente ou corrompido: começa vazio */
    }
    return m;
  }

  /** JID para responder: o LID gravado, ou o JID de telefone. */
  jid(telefone: string): string {
    return this.mapa.get(telefone) ?? `${telefone}@s.whatsapp.net`;
  }

  async lembrar(telefone: string, jidResposta: string): Promise<void> {
    if (!jidResposta.endsWith("@lid") || this.mapa.get(telefone) === jidResposta) return;
    this.mapa.set(telefone, jidResposta);
    await this.salvar();
  }

  /** Grava em arquivo temporário e renomeia: um gateway derrubado no meio não corrompe o mapa. */
  private salvar(): Promise<void> {
    this.gravacao = this.gravacao.then(async () => {
      await mkdir(path.dirname(this.arquivo), { recursive: true });
      const tmp = `${this.arquivo}.tmp`;
      await writeFile(tmp, JSON.stringify(Object.fromEntries(this.mapa)), { mode: 0o600 });
      await rename(tmp, this.arquivo);
    });
    return this.gravacao;
  }

  /** Ao desconectar o número, os contatos daquele restaurante são apagados. */
  async apagar(): Promise<void> {
    await this.gravacao;
    this.mapa.clear();
    await rm(this.arquivo, { force: true });
  }

  get tamanho(): number {
    return this.mapa.size;
  }
}
