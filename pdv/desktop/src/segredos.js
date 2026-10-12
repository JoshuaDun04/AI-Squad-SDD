"use strict";
/**
 * Segredos locais (RT-17): gerados na primeira execução e guardados na pasta de dados do usuário.
 * Trocar o arquivo invalida os logins abertos; o banco continua válido.
 */
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const ARQUIVO = "segredos.json";

function gerar() {
  return {
    jwtSecret: crypto.randomBytes(32).toString("hex"),
    gatewayToken: crypto.randomBytes(24).toString("hex"),
  };
}

function validos(s) {
  return (
    s &&
    typeof s.jwtSecret === "string" &&
    s.jwtSecret.length >= 32 &&
    typeof s.gatewayToken === "string" &&
    s.gatewayToken.length >= 16
  );
}

function carregarSegredos(dirDados) {
  const arquivo = path.join(dirDados, ARQUIVO);
  try {
    const lidos = JSON.parse(fs.readFileSync(arquivo, "utf8"));
    if (validos(lidos)) return { ...lidos, criados: false };
  } catch {
    /* primeira execução ou arquivo danificado: gera de novo */
  }
  fs.mkdirSync(dirDados, { recursive: true });
  const novos = gerar();
  const temporario = `${arquivo}.${process.pid}.tmp`;
  fs.writeFileSync(temporario, JSON.stringify(novos, null, 2), { mode: 0o600 });
  fs.renameSync(temporario, arquivo);
  return { ...novos, criados: true };
}

module.exports = { carregarSegredos, ARQUIVO };
