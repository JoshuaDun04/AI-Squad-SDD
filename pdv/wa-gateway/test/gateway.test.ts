import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, describe, it } from "node:test";

import { ClienteApiHttp, type EventoApi } from "../src/api.js";
import { criarApp, SessaoIndisponivel, tokenConfere, type Sessoes } from "../src/app.js";
import { ConfigInvalida, lerConfig } from "../src/config.js";
import { mascarar, normalizar } from "../src/normalizar.js";

const TOKEN = "token-gateway-teste-123";
const RID = "5f0b6c5e-2a1b-4c3d-9e8f-0a1b2c3d4e5f";

class SessoesFalsas implements Sessoes {
  iniciadas: string[] = [];
  encerradas: string[] = [];
  enviadas: Array<[string, string, string]> = [];
  conectado = true;
  async iniciar(id: string) {
    this.iniciadas.push(id);
  }
  async encerrar(id: string) {
    this.encerradas.push(id);
  }
  async enviar(id: string, tel: string, texto: string) {
    if (!this.conectado) throw new SessaoIndisponivel();
    this.enviadas.push([id, tel, texto]);
  }
}

async function ouvir(server: Server): Promise<string> {
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  return `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
}

describe("servidor HTTP do gateway", () => {
  const sessoes = new SessoesFalsas();
  let url = "";
  let server: Server;

  before(async () => {
    server = createServer(criarApp(sessoes, TOKEN));
    url = await ouvir(server);
  });
  after(() => server.close());

  it("exige X-Gateway-Token (RT-03)", async () => {
    for (const headers of [{}, { "X-Gateway-Token": "errado-errado-errado" }, { "X-Gateway-Token": TOKEN + "x" }]) {
      const r = await fetch(`${url}/sessoes/${RID}`, { method: "POST", headers });
      assert.equal(r.status, 401);
    }
    assert.deepEqual(sessoes.iniciadas, []);
    assert.equal((await fetch(`${url}/saude`)).status, 200);
  });

  it("inicia e encerra sessão por restaurante, validando o id", async () => {
    const h = { "X-Gateway-Token": TOKEN };
    assert.equal((await fetch(`${url}/sessoes/${RID}`, { method: "POST", headers: h })).status, 202);
    assert.equal((await fetch(`${url}/sessoes/${RID}`, { method: "DELETE", headers: h })).status, 200);
    assert.equal((await fetch(`${url}/sessoes/..%2F..%2Fetc`, { method: "POST", headers: h })).status, 400);
    assert.deepEqual(sessoes.iniciadas, [RID]);
    assert.deepEqual(sessoes.encerradas, [RID]);
  });

  it("envia mensagem e responde 409 sem sessão conectada", async () => {
    const h = { "X-Gateway-Token": TOKEN, "Content-Type": "application/json" };
    const corpo = JSON.stringify({ restaurante_id: RID, telefone: "5592991234567", texto: "Olá" });
    assert.equal((await fetch(`${url}/mensagens`, { method: "POST", headers: h, body: corpo })).status, 200);
    assert.deepEqual(sessoes.enviadas, [[RID, "5592991234567", "Olá"]]);

    sessoes.conectado = false;
    assert.equal((await fetch(`${url}/mensagens`, { method: "POST", headers: h, body: corpo })).status, 409);
    sessoes.conectado = true;

    const ruim = JSON.stringify({ restaurante_id: RID, telefone: "abc", texto: "" });
    assert.equal((await fetch(`${url}/mensagens`, { method: "POST", headers: h, body: ruim })).status, 400);
  });
});

describe("normalização de mensagens", () => {
  it("usa o número quando o JID é de telefone", () => {
    const m = normalizar({
      key: { id: "wamid-1", remoteJid: "5592991234567@s.whatsapp.net", fromMe: false },
      pushName: "Maria",
      message: { conversation: " 1 " },
    });
    assert.deepEqual(m, {
      mensagemId: "wamid-1",
      telefone: "5592991234567",
      jidResposta: "5592991234567@s.whatsapp.net",
      nomePerfil: "Maria",
      texto: "1",
    });
  });

  it("prefere o número alternativo quando chega como LID", () => {
    const m = normalizar({
      key: { id: "w2", remoteJid: "123456789012345@lid", remoteJidAlt: "5592991234567@s.whatsapp.net" },
      message: { extendedTextMessage: { text: "oi" } },
    });
    assert.equal(m?.telefone, "5592991234567");
    assert.equal(m?.texto, "oi");
  });

  it("aceita LID sem número e responde no próprio LID", () => {
    const m = normalizar({ key: { id: "w3", remoteJid: "123456789012345@lid" }, message: { conversation: "oi" } });
    assert.equal(m?.jidResposta, "123456789012345@lid");
  });

  it("ignora grupos, status, mensagens próprias e sem id", () => {
    assert.equal(normalizar({ key: { id: "a", remoteJid: "1203630@g.us" } }), null);
    assert.equal(normalizar({ key: { id: "b", remoteJid: "status@broadcast" } }), null);
    assert.equal(normalizar({ key: { id: "c", remoteJid: "5592991234567@s.whatsapp.net", fromMe: true } }), null);
    assert.equal(normalizar({ key: { remoteJid: "5592991234567@s.whatsapp.net" } }), null);
  });

  it("mídia sem texto vira texto vazio", () => {
    const m = normalizar({ key: { id: "d", remoteJid: "5592991234567@s.whatsapp.net" }, message: {} });
    assert.equal(m?.texto, "");
  });

  it("mascara telefone para logs", () => {
    assert.equal(mascarar("5592991234567"), "*****-4567");
    assert.equal(mascarar("12"), "*****");
  });
});

describe("configuração e utilidades", () => {
  it("recusa iniciar sem token forte (SEC-03)", () => {
    assert.throws(() => lerConfig({ GATEWAY_TOKEN: "curto" }), ConfigInvalida);
    assert.throws(() => lerConfig({}), ConfigInvalida);
    const c = lerConfig({ GATEWAY_TOKEN: TOKEN, API_URL: "http://api:8000/" });
    assert.equal(c.apiUrl, "http://api:8000");
    assert.equal(c.porta, 3001);
  });

  it("compara token em tempo constante", () => {
    assert.equal(tokenConfere(TOKEN, TOKEN), true);
    assert.equal(tokenConfere(undefined, TOKEN), false);
    assert.equal(tokenConfere("x", TOKEN), false);
  });
});

describe("cliente do webhook", () => {
  it("repete em erro 5xx e para em 4xx", async () => {
    const recebidos: Array<{ token: string | undefined; corpo: EventoApi }> = [];
    let falhas = 2;
    const server = createServer((req, res) => {
      let dados = "";
      req.on("data", (c) => (dados += c));
      req.on("end", () => {
        recebidos.push({ token: req.headers["x-gateway-token"] as string, corpo: JSON.parse(dados) });
        const corpo = JSON.parse(dados) as EventoApi;
        if (corpo.tipo === "status_conexao") {
          res.writeHead(422).end();
          return;
        }
        res.writeHead(falhas-- > 0 ? 503 : 200).end();
      });
    });
    const url = await ouvir(server);
    const cliente = new ClienteApiHttp(url, TOKEN, 4, 1, () => {});
    const evento: EventoApi = {
      tipo: "mensagem",
      restaurante_id: RID,
      mensagem_id: "w1",
      telefone: "5592991234567",
      nome_perfil: "Maria",
      texto: "oi",
      recebida_em: new Date().toISOString(),
    };
    assert.equal(await cliente.enviarEvento(evento), true);
    assert.equal(recebidos.length, 3);
    assert.ok(recebidos.every((r) => r.token === TOKEN));

    assert.equal(
      await cliente.enviarEvento({ tipo: "status_conexao", restaurante_id: RID, status: "conectado" }),
      false,
    );
    assert.equal(recebidos.length, 4);
    server.close();
  });
});
