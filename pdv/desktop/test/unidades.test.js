"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { describe, test } = require("node:test");

const { carregarSegredos } = require("../src/segredos");
const { enderecoLocal, escolherPorta, privado } = require("../src/rede");
const { avisosWhatsapp, precisaBackup, redePublica, rotuloServico, DIA_MS } = require("../src/rotinas");
const { caminhosRecursos, urlSqlite } = require("../src/orquestrador");

describe("segredos", () => {
  test("gera na primeira vez e reaproveita depois", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "seg-"));
    const a = carregarSegredos(dir);
    assert.equal(a.criados, true);
    assert.match(a.jwtSecret, /^[0-9a-f]{64}$/);
    assert.match(a.gatewayToken, /^[0-9a-f]{48}$/);
    const b = carregarSegredos(dir);
    assert.equal(b.criados, false);
    assert.equal(b.jwtSecret, a.jwtSecret);
    if (process.platform !== "win32") {
      assert.equal(fs.statSync(path.join(dir, "segredos.json")).mode & 0o777, 0o600);
    }
  });

  test("arquivo danificado ou fraco é substituído", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "seg-"));
    fs.writeFileSync(path.join(dir, "segredos.json"), "{quebrado");
    assert.equal(carregarSegredos(dir).criados, true);
    fs.writeFileSync(path.join(dir, "segredos.json"), JSON.stringify({ jwtSecret: "curto", gatewayToken: "x" }));
    const c = carregarSegredos(dir);
    assert.equal(c.criados, true);
    assert.ok(c.jwtSecret.length >= 32);
  });
});

describe("rede", () => {
  test("privado", () => {
    for (const ip of ["10.0.0.1", "192.168.1.5", "172.16.0.1", "172.31.255.1"]) assert.ok(privado(ip), ip);
    for (const ip of ["172.15.0.1", "172.32.0.1", "8.8.8.8", "100.64.0.1"]) assert.ok(!privado(ip), ip);
  });

  test("prefere a placa física com IP de rede doméstica", () => {
    const ip = enderecoLocal({
      "vEthernet (WSL)": [{ family: "IPv4", address: "172.20.0.1", internal: false }],
      Loopback: [{ family: "IPv4", address: "127.0.0.1", internal: true }],
      "Wi-Fi": [
        { family: "IPv6", address: "fe80::1", internal: false },
        { family: "IPv4", address: "192.168.0.10", internal: false },
      ],
      Ethernet: [{ family: 4, address: "10.1.1.2", internal: false }],
    });
    assert.equal(ip, "192.168.0.10");
    assert.equal(enderecoLocal({ VirtualBox: [{ family: "IPv4", address: "192.168.56.1", internal: false }] }), "192.168.56.1");
    assert.equal(enderecoLocal({ lo: [{ family: "IPv4", address: "127.0.0.1", internal: true }] }), null);
  });

  test("escolhe a próxima porta quando a preferida está ocupada", async () => {
    const ocupada = await escolherPorta(0);
    const s = net.createServer();
    await new Promise((r) => s.listen(ocupada, "127.0.0.1", r));
    try {
      const p = await escolherPorta(ocupada);
      assert.ok(p > ocupada && p <= ocupada + 10);
    } finally {
      s.close();
    }
  });
});

describe("rotinas", () => {
  test("backup diário", () => {
    const agora = new Date(2026, 9, 12, 10, 0, 0);
    assert.equal(precisaBackup(null, agora), true);
    assert.equal(precisaBackup(new Date(agora - DIA_MS + 60_000), agora), false);
    assert.equal(precisaBackup(new Date(agora - DIA_MS), agora), true);
  });

  test("avisos do WhatsApp só em mudança", () => {
    const con = [{ restaurante: "Sabor do Rio", status: "conectado" }];
    const des = [{ restaurante: "Sabor do Rio", status: "desconectado" }];
    assert.deepEqual(avisosWhatsapp([], con), []);
    assert.deepEqual(avisosWhatsapp(con, con), []);
    const caiu = avisosWhatsapp(con, des);
    assert.equal(caiu.length, 1);
    assert.equal(caiu[0].tipo, "caiu");
    assert.match(caiu[0].texto, /Sabor do Rio/);
    assert.equal(avisosWhatsapp(des, con)[0].tipo, "voltou");
    assert.deepEqual(avisosWhatsapp(con, []), [], "API fora do ar não gera aviso de WhatsApp");
    assert.deepEqual(avisosWhatsapp(des, [{ restaurante: "Sabor do Rio", status: "aguardando_qr" }]), []);
  });

  test("rede pública atrapalha a cozinha", () => {
    assert.equal(redePublica("Private\r\n"), false);
    assert.equal(redePublica("DomainAuthenticated\r\nPublic\r\n"), true);
    assert.equal(redePublica(""), false);
  });

  test("rótulos da bandeja", () => {
    assert.equal(rotuloServico("whatsapp", "rodando"), "WhatsApp (robô): funcionando");
    assert.match(rotuloServico("api", "falhou"), /PARADO/);
  });
});

describe("caminhos", () => {
  test("empacotado usa resources e o próprio Electron como Node", () => {
    const c = caminhosRecursos({ empacotado: true, resourcesPath: "/r", raizPdv: "/x", execPath: "/app/PDV.exe" });
    assert.equal(c.api, path.join("/r", "api"));
    assert.equal(c.web, path.join("/r", "web"));
    assert.equal(c.gateway, path.join("/r", "wa-gateway", "dist", "index.js"));
    assert.equal(c.node, "/app/PDV.exe");
    assert.equal(c.nodeEhElectron, true);
  });

  test("url do SQLite com barras normais", () => {
    assert.match(urlSqlite("/tmp/a b/pdv.sqlite"), /^sqlite:\/\/\/\/tmp\/a b\/pdv\.sqlite$/);
  });
});
