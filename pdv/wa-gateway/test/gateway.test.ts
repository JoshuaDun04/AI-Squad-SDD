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

describe("contatos LID persistidos", () => {
  it("lembra o JID LID entre reinícios e apaga ao desconectar", async () => {
    const { mkdtemp, readFile, stat } = await import("node:fs/promises");
    const { tmpdir } = await import("node:os");
    const { MapaContatos } = await import("../src/contatos.js");
    const dir = await mkdtemp(`${tmpdir()}/gw-`);

    const m1 = await MapaContatos.abrir(dir, RID);
    await m1.lembrar("123456789012345", "123456789012345@lid");
    await m1.lembrar("5592991234567", "5592991234567@s.whatsapp.net"); // número normal não é gravado
    assert.equal(m1.tamanho, 1);

    const m2 = await MapaContatos.abrir(dir, RID); // "reinício"
    assert.equal(m2.jid("123456789012345"), "123456789012345@lid");
    assert.equal(m2.jid("5592991234567"), "5592991234567@s.whatsapp.net");
    const arquivo = `${dir}/contatos/${RID}.json`;
    assert.deepEqual(JSON.parse(await readFile(arquivo, "utf8")), { "123456789012345": "123456789012345@lid" });
    assert.equal((await stat(arquivo)).mode & 0o777, 0o600);

    await m2.apagar();
    await assert.rejects(stat(arquivo));
    assert.equal((await MapaContatos.abrir(dir, RID)).tamanho, 0);
  });

  it("ignora arquivo corrompido ou com entradas inválidas", async () => {
    const { mkdtemp, mkdir, writeFile } = await import("node:fs/promises");
    const { tmpdir } = await import("node:os");
    const { MapaContatos } = await import("../src/contatos.js");
    const dir = await mkdtemp(`${tmpdir()}/gw-`);
    await mkdir(`${dir}/contatos`);
    await writeFile(`${dir}/contatos/${RID}.json`, "{nao é json");
    assert.equal((await MapaContatos.abrir(dir, RID)).tamanho, 0);
    await writeFile(`${dir}/contatos/${RID}.json`, JSON.stringify({ "../x": "a@lid", "123456789": "123456789@s.whatsapp.net", "987654321": "987654321@lid" }));
    assert.equal((await MapaContatos.abrir(dir, RID)).tamanho, 1);
  });
});

describe("revisão independente", () => {
  it("JSON malformado ou grande demais responde 4xx, não 500 (REV-12)", async () => {
    const server = createServer(criarApp(new SessoesFalsas(), TOKEN));
    const url = await ouvir(server);
    const h = { "X-Gateway-Token": TOKEN, "Content-Type": "application/json" };
    assert.equal((await fetch(`${url}/mensagens`, { method: "POST", headers: h, body: "{nao json" })).status, 400);
    const grande = JSON.stringify({ restaurante_id: RID, telefone: "5592991234567", texto: "x".repeat(40_000) });
    assert.equal((await fetch(`${url}/mensagens`, { method: "POST", headers: h, body: grande })).status, 413);
    server.close();
  });

  it("máscara profunda para logs do Baileys (REV-09)", async () => {
    const { mascararProfundo } = await import("../src/normalizar.js");
    const entrada = {
      key: { remoteJid: "5592991234567@s.whatsapp.net", id: "3EB0ABC" },
      jid: "123456789012345@lid",
      lista: ["+5592991234567"],
      err: new Error("falha 5592991234567"),
      id: "aa60f693-52c9-48f6-940d-123456789012",
      buffer: Buffer.from("abc"),
    };
    const texto = JSON.stringify(mascararProfundo(entrada));
    assert.ok(!texto.includes("5592991234567") && !texto.includes("123456789012345"), texto);
    assert.ok(texto.includes("*****-4567") && texto.includes("*****-2345"));
    assert.ok(texto.includes("aa60f693-52c9-48f6-940d-123456789012"), "UUID preservado");
    assert.ok(texto.includes("<3 bytes>"));
  });
});
