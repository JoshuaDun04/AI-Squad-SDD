"use strict";
/**
 * Servidor do painel na rede local (RF-23, RT-18): substitui o nginx da versão em servidor.
 * - entrega os arquivos do painel (com fallback para index.html nas rotas do painel);
 * - repassa /api/* para a API em 127.0.0.1, sobrescrevendo X-Forwarded-For (REV-07);
 * - nunca expõe /api/canal/* (webhook e consultas internas do gateway e do app).
 */
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const CABECALHOS_SEGURANCA = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "same-origin",
  "Content-Security-Policy":
    "default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; connect-src 'self'; " +
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
};

const TIPOS = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".txt": "text/plain; charset=utf-8",
};

const SEM_REPASSE = new Set(["connection", "keep-alive", "transfer-encoding", "upgrade", "proxy-connection", "te", "trailer"]);

function responder(res, status, corpo, tipo = "application/json; charset=utf-8", extra = {}) {
  res.writeHead(status, { ...CABECALHOS_SEGURANCA, "Content-Type": tipo, ...extra });
  res.end(corpo);
}

/** Caminho decodificado e normalizado; null se for inválido. */
function caminhoDaRequisicao(url) {
  try {
    const bruto = new URL(url, "http://painel").pathname;
    const decodificado = decodeURIComponent(bruto);
    if (decodificado.includes("\0")) return null;
    return path.posix.normalize(decodificado.replace(/\\/g, "/")).replace(/\/{2,}/g, "/");
  } catch {
    return null;
  }
}

function bloqueado(caminho) {
  const c = caminho.toLowerCase();
  return c === "/api/canal" || c.startsWith("/api/canal/");
}

function criarServidorPainel({ raiz, apiHost = "127.0.0.1", apiPorta, aoErro = () => {} }) {
  const raizAbs = path.resolve(raiz);
  const index = path.join(raizAbs, "index.html");

  function servirArquivo(req, res, caminho) {
    const alvo = path.resolve(raizAbs, `.${caminho}`);
    if (alvo !== raizAbs && !alvo.startsWith(raizAbs + path.sep)) {
      return responder(res, 404, JSON.stringify({ erro: "nao_encontrado" }));
    }
    fs.stat(alvo, (erro, info) => {
      let arquivo = alvo;
      if (erro || !info.isFile()) {
        // Rota do painel (#/cozinha etc.) ou recarregamento: entrega o index; arquivo com extensão inexistente dá 404
        if (path.extname(caminho)) return responder(res, 404, JSON.stringify({ erro: "nao_encontrado" }));
        arquivo = index;
      }
      const tipo = TIPOS[path.extname(arquivo).toLowerCase()] || "application/octet-stream";
      const cache = arquivo.includes(`${path.sep}assets${path.sep}`) ? "public, max-age=31536000, immutable" : "no-cache";
      res.writeHead(200, { ...CABECALHOS_SEGURANCA, "Content-Type": tipo, "Cache-Control": cache });
      if (req.method === "HEAD") return res.end();
      fs.createReadStream(arquivo)
        .on("error", () => res.destroy())
        .pipe(res);
    });
  }

  function repassar(req, res, caminhoApi) {
    const cabecalhos = {};
    for (const [k, v] of Object.entries(req.headers)) {
      if (!SEM_REPASSE.has(k.toLowerCase()) && k.toLowerCase() !== "x-forwarded-for") cabecalhos[k] = v;
    }
    cabecalhos["x-forwarded-for"] = req.socket.remoteAddress || "";
    cabecalhos["x-forwarded-proto"] = "http";
    const busca = new URL(req.url, "http://painel").search;
    const pedido = http.request(
      { host: apiHost, port: apiPorta, method: req.method, path: caminhoApi + busca, headers: cabecalhos },
      (resposta) => {
        const saida = {};
        for (const [k, v] of Object.entries(resposta.headers)) {
          if (!SEM_REPASSE.has(k.toLowerCase())) saida[k] = v;
        }
        res.writeHead(resposta.statusCode || 502, { ...CABECALHOS_SEGURANCA, ...saida });
        resposta.pipe(res);
      },
    );
    pedido.setTimeout(30_000, () => pedido.destroy(new Error("tempo esgotado")));
    pedido.on("error", (erro) => {
      aoErro(erro);
      if (!res.headersSent) responder(res, 502, JSON.stringify({ erro: "api_indisponivel", detalhe: "o serviço está reiniciando; tente de novo" }));
      else res.destroy();
    });
    req.pipe(pedido);
  }

  return http.createServer((req, res) => {
    const caminho = caminhoDaRequisicao(req.url || "/");
    if (caminho === null) return responder(res, 400, JSON.stringify({ erro: "requisicao_invalida" }));
    if (bloqueado(caminho)) return responder(res, 404, JSON.stringify({ erro: "nao_encontrado" }));
    if (caminho === "/api" || caminho.startsWith("/api/")) return repassar(req, res, caminho.slice(4) || "/");
    if (req.method !== "GET" && req.method !== "HEAD") return responder(res, 405, JSON.stringify({ erro: "metodo_nao_permitido" }));
    return servirArquivo(req, res, caminho);
  });
}

module.exports = { criarServidorPainel, caminhoDaRequisicao, CABECALHOS_SEGURANCA };
