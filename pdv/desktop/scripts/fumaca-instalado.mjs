// Fumaça do app instalado no Windows (CI): abre o .exe, espera ficar pronto, roda um comando
// (o e2e) com PDV_DADOS apontando para a pasta de dados, fecha o app à força e confere que a
// API e o robô não ficaram órfãos (RT-19).
//
// Uso: node scripts/fumaca-instalado.mjs --exe "<...>\PDV Restaurantes.exe" --dados "<pasta>" [-- comando args...]
import { execFileSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { parseArgs } from "node:util";

const { values, positionals } = parseArgs({
  options: { exe: { type: "string" }, dados: { type: "string" }, espera: { type: "string", default: "180" } },
  allowPositionals: true,
});
if (!values.exe || !values.dados) {
  console.error("uso: --exe <caminho> --dados <pasta> [-- comando]");
  process.exit(2);
}

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const instancia = path.join(values.dados, "instancia.json");

function obter(url) {
  return new Promise((resolve) => {
    http
      .get(url, { timeout: 5000 }, (res) => {
        let corpo = "";
        res.on("data", (d) => (corpo += d));
        res.on("end", () => resolve({ status: res.statusCode, corpo }));
      })
      .on("error", () => resolve({ status: 0, corpo: "" }));
  });
}

/** PIDs da API (python.exe embutido) e do robô (o próprio .exe rodando o gateway). */
function filhosDoApp() {
  if (process.platform !== "win32") return [];
  const pasta = path.dirname(values.exe).replace(/'/g, "''");
  const saida = execFileSync("powershell.exe", [
    "-NoProfile",
    "-Command",
    `Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '${pasta}\\resources\\*' -or $_.CommandLine -like '*wa-gateway*index.js*' } | ForEach-Object { $_.ProcessId }`,
  ]).toString();
  return saida.split(/\s+/).filter(Boolean);
}

function mostrarLogs() {
  for (const nome of ["app.log", "api.log", "whatsapp.log"]) {
    const arq = path.join(values.dados, "logs", nome);
    if (!fs.existsSync(arq)) continue;
    const fim = fs.readFileSync(arq, "utf8").slice(-3000);
    console.log(`----- ${nome}\n${fim}`);
    // No CI, vira anotação do job: dá para ler a causa sem baixar o log inteiro
    if (process.env.GITHUB_ACTIONS) {
      const escapado = fim.replace(/%/g, "%25").replace(/\r/g, "").replace(/\n/g, "%0A");
      console.log(`::warning title=${nome}::${escapado}`);
    }
  }
}

fs.rmSync(instancia, { force: true });
console.log(`abrindo ${values.exe}`);
const app = spawn(values.exe, [`--user-data-dir=${values.dados}`], { stdio: "inherit" });
let saiu = false;
app.on("exit", (c) => {
  saiu = true;
  console.log(`app saiu (código ${c})`);
});

let falha = null;
try {
  const limite = Date.now() + Number(values.espera) * 1000;
  while (!fs.existsSync(instancia)) {
    if (saiu) throw new Error("o app fechou antes de ficar pronto");
    if (Date.now() > limite) throw new Error("o app não ficou pronto a tempo");
    await esperar(1000);
  }
  const info = JSON.parse(fs.readFileSync(instancia, "utf8"));
  console.log(`pronto: ${JSON.stringify(info)}`);

  const saude = await obter(`${info.urlLocal}/api/saude`);
  if (saude.status !== 200) throw new Error(`/api/saude respondeu ${saude.status}`);
  const inst = JSON.parse((await obter(`${info.urlLocal}/api/instalacao`)).corpo);
  if (inst.modo !== "local") throw new Error(`instalação deveria estar em modo local: ${JSON.stringify(inst)}`);
  const canal = await obter(`${info.urlLocal}/api/canal/conexoes`);
  if (canal.status !== 404) throw new Error(`/api/canal deveria ser 404 pelo painel, veio ${canal.status}`);
  console.log("painel, API e bloqueio do canal ok");

  if (positionals.length) {
    const [cmd, ...args] = positionals;
    console.log(`$ ${positionals.join(" ")}`);
    const r = spawnSync(cmd, args, { stdio: ["ignore", "inherit", "pipe"], env: { ...process.env, PDV_DADOS: values.dados } });
    const erros = String(r.stderr || "");
    process.stderr.write(erros);
    if (r.status !== 0) throw new Error(`${cmd} saiu com código ${r.status}:\n${erros.slice(-2500)}`);
  }
} catch (erro) {
  falha = erro;
}

// Fecha o app à força (como uma queda) e confere que os filhos saíram sozinhos
const antes = filhosDoApp();
console.log(`API e robô antes de fechar: ${antes.join(", ") || "nenhum"}`);
if (process.platform === "win32") {
  try {
    execFileSync("taskkill", ["/PID", String(app.pid), "/F"]);
  } catch {
    /* já saiu */
  }
} else {
  app.kill("SIGKILL");
}
let restantes = [];
for (let i = 0; i < 20; i++) {
  await esperar(1000);
  restantes = filhosDoApp();
  if (!restantes.length) break;
}
if (!falha && restantes.length) falha = new Error(`processos órfãos depois de o app cair: ${restantes.join(", ")}`);

if (falha) {
  mostrarLogs();
  console.error(`FALHOU: ${falha.message}`);
  if (process.env.GITHUB_ACTIONS) console.log(`::error title=Fumaça do app instalado::${String(falha.message).replace(/%/g, "%25").replace(/\r?\n/g, "%0A")}`);
  process.exit(1);
}
console.log("fumaça ok");
