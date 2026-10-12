// Monta pdv/desktop/recursos/ com tudo que o instalador leva além do Electron (ADR-0011):
//   api/        código da API e migrações
//   python/     Python embutido do Windows + dependências da API (do requirements-windows.lock.txt, com hash)
//   wa-gateway/ gateway compilado + dependências de produção
//   web/        painel construído
//
// Uso: node scripts/preparar-recursos.mjs --python-embed <pasta do python-3.12.x-embed-amd64 extraído>
//      [--pip <comando pip do sistema>] [--sem-python]
// Pré-requisitos: `npm run build` no wa-gateway e no web.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    "python-embed": { type: "string" },
    pip: { type: "string", default: process.platform === "win32" ? "python -m pip" : "python3 -m pip" },
    "sem-python": { type: "boolean", default: false },
  },
});

const DESKTOP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PDV = path.dirname(DESKTOP);
const SAIDA = path.join(DESKTOP, "recursos");
const IGNORAR = new Set(["__pycache__", ".pytest_cache", ".mypy_cache", "tests", ".DS_Store"]);

function passo(texto) {
  console.log(`\n== ${texto}`);
}

function copiar(origem, destino) {
  if (!fs.existsSync(origem)) throw new Error(`não encontrado: ${path.relative(PDV, origem)} (rodou o build?)`);
  fs.cpSync(origem, destino, {
    recursive: true,
    filter: (p) => !IGNORAR.has(path.basename(p)) && !p.endsWith(".pyc"),
  });
}

function rodar(comando, args, opcoes = {}) {
  console.log(`$ ${comando} ${args.join(" ")}`);
  execFileSync(comando, args, { stdio: "inherit", shell: process.platform === "win32", ...opcoes });
}

fs.rmSync(SAIDA, { recursive: true, force: true });
fs.mkdirSync(SAIDA, { recursive: true });

passo("API");
const api = path.join(SAIDA, "api");
copiar(path.join(PDV, "api", "pdv_api"), path.join(api, "pdv_api"));
copiar(path.join(PDV, "api", "migracoes"), path.join(api, "migracoes"));
copiar(path.join(PDV, "api", "alembic.ini"), path.join(api, "alembic.ini"));

if (!values["sem-python"]) {
  passo("Python embutido");
  const embed = values["python-embed"];
  if (!embed) throw new Error("informe --python-embed <pasta> (ou --sem-python para pular)");
  const python = path.join(SAIDA, "python");
  copiar(path.resolve(embed), python);
  const pth = fs.readdirSync(python).find((n) => /^python3\d+\._pth$/.test(n));
  if (!pth) throw new Error("arquivo python3XX._pth não encontrado: a pasta é do Python embutido (embed-amd64)?");
  const zipStdlib = fs.readdirSync(python).find((n) => /^python3\d+\.zip$/.test(n));
  // O ._pth manda no sys.path do Python embutido (PYTHONPATH é ignorado): inclui as dependências e a API
  fs.writeFileSync(path.join(python, pth), [zipStdlib, ".", "Lib\\site-packages", "..\\api", "import site", ""].join("\r\n"));

  passo("Dependências da API (Windows x64, Python 3.12, só wheels com hash)");
  const [pipCmd, ...pipArgs] = values.pip.split(" ");
  rodar(pipCmd, [
    ...pipArgs,
    "install",
    "--disable-pip-version-check",
    "--no-compile",
    "--require-hashes",
    "--only-binary=:all:",
    "--platform", "win_amd64",
    "--python-version", "3.12",
    "--implementation", "cp",
    "--target", path.join(python, "Lib", "site-packages"),
    "-r", path.join(PDV, "api", "requirements-windows.lock.txt"),
  ]);
}

passo("Gateway do WhatsApp");
const gw = path.join(SAIDA, "wa-gateway");
copiar(path.join(PDV, "wa-gateway", "dist"), path.join(gw, "dist"));
for (const f of ["package.json", "package-lock.json"]) copiar(path.join(PDV, "wa-gateway", f), path.join(gw, f));
rodar("npm", ["ci", "--omit=dev", "--no-audit", "--no-fund"], { cwd: gw });

passo("Painel");
copiar(path.join(PDV, "web", "dist"), path.join(SAIDA, "web"));

let total = 0;
for (const nome of fs.readdirSync(SAIDA)) {
  const tamanho = Number(execFileSync(process.platform === "win32" ? "powershell" : "du", process.platform === "win32"
    ? ["-NoProfile", "-Command", `(Get-ChildItem -Recurse -File '${path.join(SAIDA, nome)}' | Measure-Object Length -Sum).Sum`]
    : ["-sb", path.join(SAIDA, nome)]).toString().trim().split(/\s/)[0]);
  total += tamanho;
  console.log(`${nome.padEnd(12)} ${(tamanho / 1048576).toFixed(1)} MB`);
}
console.log(`${"total".padEnd(12)} ${(total / 1048576).toFixed(1)} MB`);
