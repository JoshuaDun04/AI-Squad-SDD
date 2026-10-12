"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");

const { Servico } = require("../src/supervisor");

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "supervisor-"));

/** Servidor HTTP de mentira com /saude; morre sozinho depois de `vidaMs` (0 = nunca). */
function scriptServidor(vidaMs) {
  const arquivo = path.join(dir, `servidor-${vidaMs}.js`);
  fs.writeFileSync(
    arquivo,
    `const http = require("node:http");
     const s = http.createServer((q, r) => { r.writeHead(q.url === "/saude" ? 200 : 404); r.end("ok"); });
     s.listen(Number(process.env.PORTA), "127.0.0.1");
     console.log("subiu", process.pid);
     if (${vidaMs} > 0) setTimeout(() => process.exit(3), ${vidaMs});`,
  );
  return arquivo;
}

async function portaLivre() {
  const { escolherPorta } = require("../src/rede");
  return escolherPorta(0);
}

function esperar(cond, timeoutMs = 10_000) {
  return new Promise((resolve, reject) => {
    const limite = Date.now() + timeoutMs;
    const t = setInterval(() => {
      if (cond()) {
        clearInterval(t);
        resolve();
      } else if (Date.now() > limite) {
        clearInterval(t);
        reject(new Error("tempo esgotado esperando condição"));
      }
    }, 20);
  });
}

test("[BDD-APP-02] serviço que cai é reiniciado com espera crescente e avisa", async () => {
  const porta = await portaLivre();
  const log = path.join(dir, "logs", "api.log");
  const s = new Servico({
    nome: "api",
    comando: process.execPath,
    args: [scriptServidor(0)],
    env: { PORTA: String(porta) },
    urlSaude: `http://127.0.0.1:${porta}/saude`,
    arquivoLog: log,
    atrasos: [50, 100, 200],
  });
  const eventos = [];
  s.on("estado", (e) => eventos.push(e));
  s.iniciar();
  await s.aguardarSaude(10_000, 20);
  assert.equal(s.estado, "rodando");

  // Queda inesperada: mata o processo por fora
  const pid1 = s.processo.pid;
  s.processo.kill("SIGKILL");
  await esperar(() => s.estado === "reiniciando");
  const aviso = eventos.find((e) => e.estado === "reiniciando");
  assert.equal(aviso.servico, "api");
  assert.match(aviso.detalhe, /reinício em/);
  await esperar(() => s.estado === "rodando" && s.processo && s.processo.pid !== pid1);

  // Segunda queda espera mais que a primeira (backoff)
  const t0 = Date.now();
  s.processo.kill("SIGKILL");
  await esperar(() => s.estado === "rodando");
  assert.ok(Date.now() - t0 >= 100, "segunda espera usa o segundo atraso");
  assert.equal(s.quedas.length, 2);

  await s.parar();
  assert.equal(s.estado, "parado");
  assert.equal(s.processo, null);
  const texto = fs.readFileSync(log, "utf8");
  assert.match(texto, /iniciando api/);
  assert.match(texto, /subiu/);
  assert.match(texto, /api saiu/);
});

test("[BDD-APP-03] serviço que cai sem parar é dado como falho e o dono é avisado", async () => {
  const s = new Servico({
    nome: "whatsapp",
    comando: process.execPath,
    args: ["-e", "process.exit(1)"],
    atrasos: [10],
    maxFalhas: 3,
  });
  const falhas = [];
  s.on("falhou", (e) => falhas.push(e));
  const estados = [];
  s.on("estado", (e) => estados.push(e.estado));
  s.iniciar();
  await esperar(() => s.estado === "falhou");
  // Para de tentar: nenhum processo e nenhum reinício agendado
  await new Promise((r) => setTimeout(r, 100));
  assert.equal(s.estado, "falhou");
  assert.equal(s.processo, null);
  assert.deepEqual(falhas, [{ servico: "whatsapp" }]);
  assert.equal(estados.filter((e) => e === "iniciando").length, 4, "1 início + 3 reinícios");

  // "Tentar de novo" recomeça a contagem
  s.zerarQuedas();
  assert.equal(s.quedas.length, 0);
  await s.parar();
});

test("parar não reinicia e quedas antigas saem da janela", async () => {
  const s = new Servico({ nome: "x", comando: process.execPath, args: ["-e", "setInterval(()=>{},1000)"], janelaMs: 50 });
  s.iniciar();
  assert.equal(s.estado, "rodando", "sem urlSaude fica rodando direto");
  await s.parar();
  await new Promise((r) => setTimeout(r, 50));
  assert.equal(s.estado, "parado");
  assert.equal(s.processo, null);
  s.quedas = [Date.now() - 1000];
  s._agendarReinicio(1);
  assert.equal(s.quedas.length, 1, "queda antiga descartada");
  await s.parar();
});

test("aguardarSaude falha se o processo morre antes de ficar pronto", async () => {
  const s = new Servico({
    nome: "y",
    comando: process.execPath,
    args: ["-e", "process.exit(2)"],
    urlSaude: "http://127.0.0.1:1/saude",
    atrasos: [60_000],
  });
  s.iniciar();
  await assert.rejects(s.aguardarSaude(5000, 20), /terminou antes de ficar pronto/);
  await s.parar();
});
