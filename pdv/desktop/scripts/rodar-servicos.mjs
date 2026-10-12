// Sobe API, robô e painel sem o Electron (CI e desenvolvimento).
// Uso: node scripts/rodar-servicos.mjs --dados <pasta> [--recursos <pasta empacotada>] [--porta 8080]
// Fica no ar até receber Ctrl+C ou SIGTERM.
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const require = createRequire(import.meta.url);
const { Orquestrador, caminhosRecursos } = require("../src/orquestrador.js");

const { values } = parseArgs({
  options: {
    dados: { type: "string" },
    recursos: { type: "string" },
    porta: { type: "string", default: "8080" },
    host: { type: "string", default: "127.0.0.1" },
  },
});
if (!values.dados) {
  console.error("informe --dados <pasta>");
  process.exit(2);
}

const raizPdv = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const caminhos = values.recursos
  ? { ...caminhosRecursos({ empacotado: true, resourcesPath: path.resolve(values.recursos) }), node: process.execPath, nodeEhElectron: false }
  : caminhosRecursos({ empacotado: false, raizPdv });

const orq = new Orquestrador({
  dirDados: path.resolve(values.dados),
  caminhos,
  portaPainel: Number(values.porta),
  hostPainel: values.host,
});
orq.on("etapa", (e) => console.log(`... ${e}`));
orq.on("estado", (e) => console.log(`${e.servico}: ${e.estado}${e.detalhe ? ` (${e.detalhe})` : ""}`));

let parando = false;
async function parar() {
  if (parando) return;
  parando = true;
  await orq.parar();
  process.exit(0);
}
process.on("SIGINT", parar);
process.on("SIGTERM", parar);

try {
  const info = await orq.iniciar();
  console.log(`pronto: ${info.urlLocal}`);
} catch (erro) {
  console.error(`falhou: ${erro.message}`);
  await orq.parar().catch(() => {});
  process.exit(1);
}
