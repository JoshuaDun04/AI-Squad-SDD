"use strict";
/**
 * Integração do app sem o Electron: sobe a API real (Python), o gateway compilado e o painel
 * construído, como no computador do restaurante. Precisa de `npm run build` no wa-gateway e no web.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { after, before, describe, test } = require("node:test");

const { Orquestrador, caminhosRecursos } = require("../src/orquestrador");

const RAIZ_PDV = path.join(__dirname, "..", "..");
const caminhos = caminhosRecursos({ empacotado: false, raizPdv: RAIZ_PDV, execPath: process.execPath });
const faltando = [caminhos.gateway, path.join(caminhos.web, "index.html")].filter((p) => !fs.existsSync(p));

function pedir(porta, metodo, caminho, corpo, cabecalhos = {}) {
  return new Promise((resolve, reject) => {
    const dados = corpo ? JSON.stringify(corpo) : undefined;
    const req = http.request(
      {
        host: "127.0.0.1",
        port: porta,
        method: metodo,
        path: caminho,
        headers: { ...(dados ? { "content-type": "application/json" } : {}), ...cabecalhos },
      },
      (res) => {
        let texto = "";
        res.on("data", (d) => (texto += d));
        res.on("end", () => {
          let json = null;
          try {
            json = JSON.parse(texto);
          } catch {
            /* html */
          }
          resolve({ status: res.statusCode, json, texto });
        });
      },
    );
    req.on("error", reject);
    if (dados) req.write(dados);
    req.end();
  });
}

const SABOR = { nome: "Sabor do Rio", admin_email: "dono@sabor.com", admin_senha: "Forte#2026" };

describe("orquestrador", { skip: faltando.length ? `falta construir: ${faltando.join(", ")}` : false, timeout: 180_000 }, () => {
  let orq;
  let info;
  let dirDados;
  const etapas = [];

  before(async () => {
    dirDados = fs.mkdtempSync(path.join(os.tmpdir(), "pdv-app-"));
    orq = new Orquestrador({ dirDados, caminhos, portaPainel: 0, hostPainel: "127.0.0.1" });
    orq.on("etapa", (e) => etapas.push(e));
    info = await orq.iniciar();
  });

  after(async () => {
    if (orq) await orq.parar();
  });

  test("[BDD-APP-01] sobe API, robô e painel, e eles seguem no ar", async () => {
    assert.deepEqual(etapas, ["Preparando o banco de dados", "Iniciando o sistema", "Conectando o WhatsApp"]);
    assert.equal(orq.servicos.api.estado, "rodando");
    assert.equal(orq.servicos.gateway.estado, "rodando");
    assert.ok(fs.existsSync(path.join(dirDados, "pdv.sqlite")));
    assert.ok(fs.existsSync(path.join(dirDados, "segredos.json")));
    const instancia = JSON.parse(fs.readFileSync(path.join(dirDados, "instancia.json"), "utf8"));
    assert.equal(instancia.portaApi, info.portaApi);
    assert.ok(!JSON.stringify(instancia).includes(info.gatewayToken), "instancia.json não leva segredos");

    // Painel e API pelo servidor do painel
    const index = await pedir(info.portaPainel, "GET", "/");
    assert.equal(index.status, 200);
    assert.match(index.texto, /<div id="root">|<script/);
    assert.equal((await pedir(info.portaPainel, "GET", "/api/saude")).status, 200);

    // Primeiro uso: cadastro aberto, depois fechado (RN-24)
    const inst = await pedir(info.portaPainel, "GET", "/api/instalacao");
    assert.equal(inst.json.modo, "local");
    assert.equal(inst.json.cadastro_aberto, true);
    assert.equal((await pedir(info.portaPainel, "POST", "/api/restaurantes", SABOR)).status, 201);
    assert.equal((await pedir(info.portaPainel, "GET", "/api/instalacao")).json.cadastro_aberto, false);
    const segundo = await pedir(info.portaPainel, "POST", "/api/restaurantes", { ...SABOR, nome: "Outro", admin_email: "o@o.com" });
    assert.equal(segundo.status, 409);

    // O app consulta o WhatsApp direto na API, com o token do gateway
    const conexoes = await orq.conexoes();
    assert.equal(conexoes.length, 1);
    assert.equal(conexoes[0].restaurante, "Sabor do Rio");

    // API e gateway não aceitam conexões de fora desta máquina: só ouvem em 127.0.0.1
    const login = await pedir(info.portaPainel, "POST", "/api/auth/login", { email: SABOR.admin_email, senha: SABOR.admin_senha });
    assert.equal(login.status, 200);
    assert.equal((await pedir(info.portaGateway, "GET", "/saude")).status, 200);

    // Senha do dono esquecida (RF-28): o app redefine pelo computador e a senha antiga para de valer
    await orq.redefinirSenha(SABOR.admin_email, "Nova#Senha2026");
    assert.equal((await pedir(info.portaPainel, "POST", "/api/auth/login", { email: SABOR.admin_email, senha: SABOR.admin_senha })).status, 401);
    assert.equal((await pedir(info.portaPainel, "POST", "/api/auth/login", { email: SABOR.admin_email, senha: "Nova#Senha2026" })).status, 200);
    await assert.rejects(orq.redefinirSenha("ninguem@x.com", "Nova#Senha2026"), /administrador/);
    await orq.redefinirSenha(SABOR.admin_email, SABOR.admin_senha);

    // "Fechar a janela" no app só esconde: nenhum serviço é parado. Aqui, passado um tempo, seguem rodando.
    await new Promise((r) => setTimeout(r, 1500));
    assert.equal(orq.servicos.api.estado, "rodando");
    assert.equal(orq.servicos.gateway.estado, "rodando");
    assert.equal(orq.servicos.api.quedas.length, 0);
  });

  test("backup e restauração com os serviços no ar (RF-24)", async () => {
    const b = await orq.backup("manual");
    assert.ok(fs.existsSync(b.arquivo));
    assert.ok(orq.ultimoBackup() instanceof Date);

    // Depois do backup entra um dado novo; restaurar volta ao estado do backup
    const token = (await pedir(info.portaPainel, "POST", "/api/auth/login", { email: SABOR.admin_email, senha: SABOR.admin_senha })).json;
    assert.ok(token);
    const r = await orq.restaurar(b.arquivo);
    assert.equal(r.ok, true);
    assert.equal(orq.servicos.api.estado, "rodando");
    assert.equal(orq.servicos.gateway.estado, "rodando");
    assert.equal((await pedir(info.portaPainel, "GET", "/api/instalacao")).json.cadastro_aberto, false);

    // Arquivo que não é backup é recusado e os serviços voltam
    const falso = path.join(dirDados, "falso.sqlite");
    fs.writeFileSync(falso, "nao sou banco");
    await assert.rejects(orq.restaurar(falso));
    assert.equal(orq.servicos.api.estado, "rodando");
    assert.equal((await pedir(info.portaPainel, "GET", "/api/saude")).status, 200);
  });

  test("parar derruba tudo", async () => {
    await orq.parar();
    assert.equal(orq.servicos.api.estado, "parado");
    assert.equal(orq.servicos.gateway.estado, "parado");
    await assert.rejects(pedir(info.portaApi, "GET", "/saude"));
    await assert.rejects(pedir(info.portaPainel, "GET", "/"));
    assert.ok(!fs.existsSync(path.join(dirDados, "instancia.json")));
    orq = null;
  });
});
