"use strict";
/**
 * App PDV Restaurantes para Windows (ADR-0011, RF-22).
 * Sobe a API, o robô do WhatsApp e o painel; fica na bandeja; faz backup e se atualiza sozinho.
 */
const { execFile } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const {
  app,
  BrowserWindow,
  Menu,
  Notification,
  Tray,
  clipboard,
  dialog,
  ipcMain,
  nativeImage,
  powerSaveBlocker,
  shell,
} = require("electron");

const { Orquestrador, caminhosRecursos } = require("./orquestrador");
const { avisosWhatsapp, precisaBackup, redePublica, rotuloServico } = require("./rotinas");

const ID_APP = "br.com.pdvrestaurantes.app";
const INTERVALO_WHATSAPP_MS = 30_000;
const INTERVALO_BACKUP_MS = 60 * 60 * 1000;
const INTERVALO_ATUALIZACAO_MS = 6 * 60 * 60 * 1000;

if (!app.requestSingleInstanceLock()) {
  app.quit();
  process.exit(0);
}
app.setAppUserModelId(ID_APP);

const dirDados = app.getPath("userData"); // %APPDATA%\PDV Restaurantes
const iniciouOculto = process.argv.includes("--oculto");

let janela = null;
let janelaSenha = null;
let bandeja = null;
let orq = null;
let info = null;
let saindo = false;
let avisouBandeja = false;
let atualizacaoPronta = false;
let conexoesAnteriores = [];
const estados = { api: "parado", whatsapp: "parado" };
const temporizadores = [];

function log(texto) {
  try {
    fs.mkdirSync(path.join(dirDados, "logs"), { recursive: true });
    fs.appendFileSync(path.join(dirDados, "logs", "app.log"), `${new Date().toISOString()} ${texto}\n`);
  } catch {
    /* melhor esforço */
  }
}

function icone(nome) {
  return nativeImage.createFromPath(path.join(__dirname, nome));
}

function notificar(titulo, texto, aoClicar = mostrarJanela) {
  if (!Notification.isSupported()) return;
  const n = new Notification({ title: titulo, body: texto, icon: path.join(__dirname, "icone.png") });
  n.on("click", aoClicar);
  n.show();
}

// ---------- janela ----------

function criarJanela() {
  janela = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: "PDV Restaurantes",
    icon: path.join(__dirname, "icone.png"),
    backgroundColor: "#e9eee8",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false },
  });
  janela.removeMenu();
  janela.loadFile(path.join(__dirname, "carregando.html"));
  janela.once("ready-to-show", () => {
    if (!iniciouOculto) janela.show();
  });

  // Fechar a janela não para o robô (BDD-APP-01): só esconde
  janela.on("close", (e) => {
    if (saindo) return;
    e.preventDefault();
    janela.hide();
    if (!avisouBandeja) {
      avisouBandeja = true;
      notificar("O PDV continua funcionando", "Os pedidos seguem chegando. Para abrir de novo, use o ícone perto do relógio.");
    }
  });

  // Windows desligando ou saindo da conta: backup e parada limpa enquanto der tempo
  janela.on("session-end", () => {
    encerrar();
  });

  // Só o painel local abre dentro do app; links externos vão para o navegador
  const permitido = (url) => info && url.startsWith(info.urlLocal);
  janela.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url) && !permitido(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  janela.webContents.on("will-navigate", (e, url) => {
    if (!permitido(url)) e.preventDefault();
  });
}

function mostrarJanela() {
  if (!janela) return;
  if (janela.isMinimized()) janela.restore();
  janela.show();
  janela.focus();
}

function mostrarEtapa(texto) {
  if (!janela || !janela.webContents.getURL().startsWith("file:")) return;
  janela.webContents
    .executeJavaScript(`document.getElementById("etapa").textContent = ${JSON.stringify(texto)};`)
    .catch(() => {});
}

// ---------- bandeja ----------

function atualizarBandeja() {
  if (!bandeja) return;
  const endereco = info?.enderecoRede;
  const itens = [
    { label: "Abrir painel", click: mostrarJanela, enabled: Boolean(info) },
    {
      label: endereco ? `Endereço da cozinha: ${endereco} (copiar)` : "Endereço da cozinha: sem rede local",
      enabled: Boolean(endereco),
      click: () => {
        clipboard.writeText(endereco);
        notificar("Endereço copiado", `Abra ${endereco} no navegador do tablet da cozinha.`);
      },
    },
    { type: "separator" },
    { label: rotuloServico("api", estados.api), enabled: false },
    { label: rotuloServico("whatsapp", estados.whatsapp), enabled: false },
  ];
  if (estados.api === "falhou" || estados.whatsapp === "falhou") {
    itens.push({ label: "Tentar iniciar de novo", click: tentarDeNovo });
  }
  itens.push(
    { type: "separator" },
    { label: "Fazer backup agora", click: () => fazerBackup("manual", true), enabled: Boolean(info) },
    { label: "Restaurar backup…", click: restaurarBackup, enabled: Boolean(info) },
    { label: "Redefinir senha do dono…", click: abrirRedefinirSenha, enabled: Boolean(info) },
    { label: "Abrir pasta de dados", click: () => shell.openPath(dirDados) },
    { type: "separator" },
    atualizacaoPronta
      ? { label: "Reiniciar e instalar atualização", click: instalarAtualizacao }
      : { label: "Verificar atualizações", click: () => verificarAtualizacoes(true), enabled: app.isPackaged },
    { label: `Versão ${app.getVersion()}`, enabled: false },
    { type: "separator" },
    { label: "Sair", click: confirmarSaida },
  );
  bandeja.setContextMenu(Menu.buildFromTemplate(itens));
  const problema = estados.api !== "rodando" || estados.whatsapp !== "rodando";
  bandeja.setToolTip(problema && info ? "PDV Restaurantes — atenção" : "PDV Restaurantes");
}

function criarBandeja() {
  bandeja = new Tray(icone("icone.png").resize({ width: 16, height: 16 }));
  bandeja.on("click", mostrarJanela);
  bandeja.on("double-click", mostrarJanela);
  atualizarBandeja();
}

// ---------- serviços ----------

async function iniciarServicos() {
  orq = new Orquestrador({ dirDados, caminhos: caminhosRecursos({
    empacotado: app.isPackaged,
    resourcesPath: process.resourcesPath,
    raizPdv: path.join(__dirname, "..", ".."),
  }) });
  orq.on("etapa", mostrarEtapa);
  orq.on("estado", ({ servico, estado, detalhe }) => {
    estados[servico] = estado;
    log(`${servico}: ${estado}${detalhe ? ` (${detalhe})` : ""}`);
    if (estado === "reiniciando" && info) {
      notificar(`${rotuloServico(servico, estado)}`, "O PDV está se recuperando sozinho; aguarde alguns segundos.");
    }
    atualizarBandeja();
  });
  orq.on("falhou", ({ servico }) => {
    log(`${servico}: desistiu depois de muitas quedas`);
    notificar(
      `${rotuloServico(servico, "falhou")}`,
      "O PDV não conseguiu se recuperar. Clique para tentar de novo ou abra a pasta de dados (logs).",
      tentarDeNovo,
    );
  });

  try {
    info = await orq.iniciar();
  } catch (erro) {
    log(`falha ao iniciar: ${erro.message}`);
    await orq.parar().catch(() => {});
    const { response } = await dialog.showMessageBox({
      type: "error",
      title: "PDV Restaurantes",
      message: "Não foi possível iniciar o PDV.",
      detail: `${erro.message}\n\nSe o problema continuar, envie a pasta "logs" ao suporte.`,
      buttons: ["Tentar de novo", "Abrir pasta de dados", "Sair"],
      defaultId: 0,
      cancelId: 2,
      noLink: true,
    });
    if (response === 0) return iniciarServicos();
    if (response === 1) shell.openPath(dirDados);
    saindo = true;
    return app.quit();
  }

  log(`pronto: painel em ${info.urlLocal}, rede ${info.enderecoRede || "-"}`);
  janela.loadURL(info.urlLocal);
  atualizarBandeja();
  verificarPerfilDeRede();

  temporizadores.push(setInterval(verificarWhatsapp, INTERVALO_WHATSAPP_MS));
  verificarBackupDiario();
  temporizadores.push(setInterval(verificarBackupDiario, INTERVALO_BACKUP_MS));
}

/** Rede marcada como Pública bloqueia o tablet da cozinha (regra do firewall é só para rede privada). */
function verificarPerfilDeRede() {
  if (process.platform !== "win32" || !info?.enderecoRede) return;
  execFile(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-Command", "Get-NetConnectionProfile | ForEach-Object { $_.NetworkCategory }"],
    { windowsHide: true, timeout: 15_000 },
    (erro, saida) => {
      if (erro || !redePublica(saida)) return;
      log("rede marcada como Pública");
      notificar(
        "A cozinha pode não conseguir abrir o painel",
        "A rede deste computador está como \"Pública\". Em Configurações > Rede e Internet, mude para \"Privada\".",
        () => shell.openExternal("ms-settings:network-status"),
      );
    },
  );
}

async function tentarDeNovo() {
  if (!orq) return;
  for (const s of Object.values(orq.servicos)) {
    if (s.estado !== "falhou") continue;
    s.zerarQuedas();
    s.iniciar();
    s.aguardarSaude().catch((e) => log(`${s.nome}: ${e.message}`));
  }
}

async function verificarWhatsapp() {
  if (!orq) return;
  const atuais = await orq.conexoes();
  for (const aviso of avisosWhatsapp(conexoesAnteriores, atuais)) notificar(aviso.titulo, aviso.texto);
  if (atuais.length) conexoesAnteriores = atuais;
}

// ---------- backup ----------

async function fazerBackup(motivo, avisar = false) {
  if (!orq) return null;
  try {
    const r = await orq.backup(motivo);
    log(`backup ${motivo}: ${path.basename(r.arquivo || "")}`);
    if (avisar) notificar("Backup feito", "Uma cópia dos dados foi guardada na pasta de backups.", () => shell.openPath(orq.dirBackups));
    return r;
  } catch (erro) {
    log(`backup ${motivo} falhou: ${erro.message}`);
    notificar("Backup não foi feito", erro.message, () => shell.openPath(dirDados));
    return null;
  }
}

function verificarBackupDiario() {
  if (orq && precisaBackup(orq.ultimoBackup())) fazerBackup("diario");
}

async function restaurarBackup() {
  if (!orq) return;
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: "Escolha o backup a restaurar",
    defaultPath: orq.dirBackups,
    filters: [{ name: "Backup do PDV", extensions: ["sqlite"] }],
    properties: ["openFile"],
  });
  if (canceled || !filePaths.length) return;
  const { response } = await dialog.showMessageBox({
    type: "warning",
    title: "Restaurar backup",
    message: `Trocar os dados atuais pelo backup "${path.basename(filePaths[0])}"?`,
    detail: "Pedidos feitos depois desse backup somem. Antes de trocar, o PDV guarda uma cópia dos dados atuais.",
    buttons: ["Restaurar", "Cancelar"],
    defaultId: 1,
    cancelId: 1,
    noLink: true,
  });
  if (response !== 0) return;
  try {
    await orq.restaurar(filePaths[0]);
    log(`restaurado: ${path.basename(filePaths[0])}`);
    janela.loadURL(info.urlLocal);
    notificar("Backup restaurado", "Entre de novo no painel.");
  } catch (erro) {
    log(`restauração falhou: ${erro.message}`);
    dialog.showErrorBox("Não foi possível restaurar", `${erro.message}\n\nOs dados atuais não foram alterados.`);
  }
}

// ---------- senha do dono esquecida (RF-28) ----------

function abrirRedefinirSenha() {
  if (janelaSenha) return janelaSenha.focus();
  janelaSenha = new BrowserWindow({
    width: 440,
    height: 430,
    resizable: false,
    minimizable: false,
    maximizable: false,
    title: "Redefinir senha do dono",
    icon: path.join(__dirname, "icone.png"),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "senha-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });
  janelaSenha.removeMenu();
  janelaSenha.webContents.on("will-navigate", (e) => e.preventDefault());
  janelaSenha.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  janelaSenha.loadFile(path.join(__dirname, "senha.html"));
  janelaSenha.on("closed", () => {
    janelaSenha = null;
  });
}

ipcMain.handle("redefinir-senha", async (evento, email, senha) => {
  // Só a janela de senha pode pedir isso
  if (!janelaSenha || evento.sender !== janelaSenha.webContents || !orq) return { ok: false, erro: "janela inválida" };
  try {
    await orq.redefinirSenha(email, senha);
    log("senha do dono redefinida no computador");
    return { ok: true };
  } catch (erro) {
    return { ok: false, erro: erro.message };
  }
});

// ---------- atualização (RF-25) ----------

let autoUpdater = null;

function configurarAtualizacoes() {
  if (!app.isPackaged) return;
  ({ autoUpdater } = require("electron-updater"));
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.logger = { info: log, warn: log, error: log, debug: () => {} };
  autoUpdater.on("update-downloaded", (u) => {
    atualizacaoPronta = true;
    atualizarBandeja();
    notificar(
      `Atualização ${u.version} pronta`,
      "Ela será instalada quando o PDV for fechado, ou clique para reiniciar agora (fora do horário de pedidos).",
      instalarAtualizacao,
    );
  });
  verificarAtualizacoes(false);
  temporizadores.push(setInterval(() => verificarAtualizacoes(false), INTERVALO_ATUALIZACAO_MS));
}

async function verificarAtualizacoes(avisar) {
  if (!autoUpdater) return;
  try {
    const r = await autoUpdater.checkForUpdates();
    if (avisar && (!r || !r.isUpdateAvailable)) notificar("PDV atualizado", `Você já está na versão ${app.getVersion()}.`);
    else if (avisar) notificar("Baixando atualização", `Versão ${r.updateInfo.version}.`);
  } catch (erro) {
    log(`atualização: ${erro.message}`);
    if (avisar) notificar("Não foi possível verificar atualizações", "Confira a internet e tente mais tarde.");
  }
}

async function instalarAtualizacao() {
  await encerrar();
  autoUpdater.quitAndInstall(true, true);
}

// ---------- saída ----------

async function confirmarSaida() {
  const { response } = await dialog.showMessageBox({
    type: "question",
    title: "Sair do PDV",
    message: "Fechar o PDV de vez?",
    detail: "Enquanto estiver fechado, o robô não responde no WhatsApp e a cozinha não recebe pedidos.",
    buttons: ["Sair", "Cancelar"],
    defaultId: 1,
    cancelId: 1,
    noLink: true,
  });
  if (response === 0) {
    await encerrar();
    app.quit();
  }
}

let encerrando = null;
function encerrar() {
  if (encerrando) return encerrando;
  saindo = true;
  temporizadores.forEach(clearInterval);
  encerrando = (async () => {
    if (orq && info) await fazerBackup("saida");
    if (orq) await orq.parar().catch((e) => log(`parar: ${e.message}`));
  })();
  return encerrando;
}

// ---------- ciclo de vida ----------

app.on("second-instance", mostrarJanela);
app.on("window-all-closed", () => {
  /* continua na bandeja */
});
app.on("before-quit", (e) => {
  if (encerrando) return;
  e.preventDefault();
  encerrar().finally(() => app.quit());
});

app.whenReady().then(() => {
  if (app.isPackaged) {
    // Abre com o Windows, direto na bandeja (RF-22)
    app.setLoginItemSettings({ openAtLogin: true, args: ["--oculto"] });
  }
  powerSaveBlocker.start("prevent-app-suspension");
  Menu.setApplicationMenu(null);
  criarJanela();
  criarBandeja();
  configurarAtualizacoes();
  iniciarServicos();
});
