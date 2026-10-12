"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { after, before, describe, test } = require("node:test");

const { criarServidorPainel, caminhoDaRequisicao, CABECALHOS_SEGURANCA } = require("../src/servidor-painel");

function ouvir(servidor) {
  return new Promise((r) => servidor.listen(0, "127.0.0.1", () => r(servidor.address().port)));
}

/** GET/POST cru (sem normalizar o caminho, para testar "/../"). */
function pedir(porta, metodo, caminho, { corpo, cabecalhos = {} } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port: porta, method: metodo, path: caminho, headers: cabecalhos }, (res) => {
      let dados = "";
      res.on("data", (d) => (dados += d));
      res.on("end", () => resolve({ status: res.statusCode, cabecalhos: res.headers, corpo: dados }));
    });
    req.on("error", reject);
    if (corpo) req.write(corpo);
    req.end();
  });
}

/** Pedido com caminho bruto via socket, para "/../segredos.json" chegar sem normalizar. */
function pedirBruto(porta, linha) {
  return new Promise((resolve, reject) => {
    const s = net.connect(porta, "127.0.0.1", () => s.write(`${linha}\r\nHost: x\r\nConnection: close\r\n\r\n`));
    let dados = "";
    s.on("data", (d) => (dados += d));
    s.on("end", () => resolve(Number(dados.split(" ")[1])));
    s.on("error", reject);
  });
}

describe("servidor do painel", () => {
  let raiz;
  let api;
  let painel;
  let portaPainel;
  const recebidos = [];

  before(async () => {
    const base = fs.mkdtempSync(path.join(os.tmpdir(), "painel-"));
    raiz = path.join(base, "web");
    fs.mkdirSync(path.join(raiz, "assets"), { recursive: true });
    fs.writeFileSync(path.join(raiz, "index.html"), "<!doctype html><title>PDV</title>");
    fs.writeFileSync(path.join(raiz, "assets", "app-123.js"), "console.log(1)");
    fs.writeFileSync(path.join(base, "segredos.json"), '{"jwtSecret":"nao-pode-vazar"}');

    api = http.createServer((req, res) => {
      let corpo = "";
      req.on("data", (d) => (corpo += d));
      req.on("end", () => {
        recebidos.push({ metodo: req.method, url: req.url, xff: req.headers["x-forwarded-for"], corpo });
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ status: "ok", url: req.url }));
      });
    });
    const portaApi = await ouvir(api);
    painel = criarServidorPainel({ raiz, apiPorta: portaApi });
    portaPainel = await ouvir(painel);
  });

  after(() => {
    painel.close();
    api.close();
  });

  test("[BDD-PNL-01] entrega o painel com cabeçalhos de segurança e repassa /api para a API", async () => {
    const r = await pedir(portaPainel, "GET", "/");
    assert.equal(r.status, 200);
    assert.match(r.corpo, /<title>PDV<\/title>/);
    for (const [k, v] of Object.entries(CABECALHOS_SEGURANCA)) assert.equal(r.cabecalhos[k.toLowerCase()], v);
    assert.equal(r.cabecalhos["cache-control"], "no-cache");

    const ativo = await pedir(portaPainel, "GET", "/assets/app-123.js");
    assert.equal(ativo.status, 200);
    assert.match(ativo.cabecalhos["content-type"], /javascript/);
    assert.match(ativo.cabecalhos["cache-control"], /immutable/);

    const saude = await pedir(portaPainel, "GET", "/api/saude?x=1", { cabecalhos: { "X-Forwarded-For": "6.6.6.6" } });
    assert.equal(saude.status, 200);
    assert.deepEqual(JSON.parse(saude.corpo), { status: "ok", url: "/saude?x=1" });
    const ultimo = recebidos.at(-1);
    // O IP informado pelo cliente é descartado: vale o endereço real da conexão (REV-07)
    assert.equal(ultimo.xff, "127.0.0.1");
    assert.equal(saude.cabecalhos["x-frame-options"], "DENY");

    const post = await pedir(portaPainel, "POST", "/api/auth/login", {
      corpo: '{"email":"a@b.c"}',
      cabecalhos: { "content-type": "application/json" },
    });
    assert.equal(post.status, 200);
    assert.equal(recebidos.at(-1).metodo, "POST");
    assert.equal(recebidos.at(-1).corpo, '{"email":"a@b.c"}');
  });

  test("[BDD-PNL-02] rotas do painel recarregadas recebem o index.html", async () => {
    for (const rota of ["/qualquer/rota", "/cozinha", "/relatorio"]) {
      const r = await pedir(portaPainel, "GET", rota);
      assert.equal(r.status, 200, rota);
      assert.match(r.corpo, /<title>PDV<\/title>/);
    }
    const head = await pedir(portaPainel, "HEAD", "/cozinha");
    assert.equal(head.status, 200);
    assert.equal(head.corpo, "");
    // Arquivo com extensão que não existe é 404, não o index (evita JS quebrado em cache)
    assert.equal((await pedir(portaPainel, "GET", "/assets/sumiu.js")).status, 404);
    assert.equal((await pedir(portaPainel, "POST", "/cozinha")).status, 405);
  });

  test("[BDD-PNL-03] /api/canal e arquivos fora do painel dão 404 sem chegar à API", async () => {
    const antes = recebidos.length;
    for (const caminho of ["/api/canal/webhook", "/api/canal", "/api/CANAL/conexoes", "/api/%63anal/webhook", "/api//canal/x", "/api/x/../canal/webhook"]) {
      const r = await pedir(portaPainel, "POST", caminho, { corpo: "{}" });
      assert.equal(r.status, 404, caminho);
    }
    assert.equal(await pedirBruto(portaPainel, "GET /../segredos.json HTTP/1.1"), 404);
    assert.equal(await pedirBruto(portaPainel, "GET /%2e%2e/segredos.json HTTP/1.1"), 404);
    assert.equal(await pedirBruto(portaPainel, "GET /assets/..%5c..%5csegredos.json HTTP/1.1"), 404);
    assert.equal((await pedir(portaPainel, "GET", "/%00")).status, 400);
    assert.equal(recebidos.length, antes, "nada foi repassado para a API");
  });

  test("API fora do ar responde 502 em JSON", async () => {
    const morto = criarServidorPainel({ raiz, apiPorta: 1 });
    const porta = await ouvir(morto);
    const r = await pedir(porta, "GET", "/api/saude");
    morto.close();
    assert.equal(r.status, 502);
    assert.equal(JSON.parse(r.corpo).erro, "api_indisponivel");
  });

  test("caminhoDaRequisicao normaliza e rejeita inválidos", () => {
    assert.equal(caminhoDaRequisicao("/a/../b"), "/b");
    assert.equal(caminhoDaRequisicao("/a%2F..%2Fb"), "/b");
    assert.equal(caminhoDaRequisicao("/%E0%A4%A"), null);
  });
});
