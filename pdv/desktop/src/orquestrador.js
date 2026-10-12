"use strict";
/**
 * Sobe e derruba as peças do PDV no computador do restaurante (ADR-0011):
 * migra o banco, inicia a API e o gateway (só em 127.0.0.1) e o servidor do painel na rede local.
 * Não depende do Electron: os testes rodam este módulo com Node puro.
 */
const childProcess = require("node:child_process");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const { enderecoLocal, escolherPorta } = require("./rede");
const { carregarSegredos } = require("./segredos");
const { criarServidorPainel } = require("./servidor-painel");
const { Servico } = require("./supervisor");

const PORTA_PAINEL = 8080;

/**
 * Onde estão a API, o Python, o gateway e o painel.
 * Empacotado: dentro de resources/. Em desenvolvimento: no repositório.
 */
function caminhosRecursos({ empacotado, resourcesPath, raizPdv, execPath = process.execPath }) {
  if (empacotado) {
    return {
      api: path.join(resourcesPath, "api"),
      python: path.join(resourcesPath, "python", process.platform === "win32" ? "python.exe" : "bin/python3"),
      gateway: path.join(resourcesPath, "wa-gateway", "dist", "index.js"),
      web: path.join(resourcesPath, "web"),
      node: execPath,
      nodeEhElectron: true,
    };
  }
  return {
    api: path.join(raizPdv, "api"),
    python: process.env.PDV_PYTHON || (process.platform === "win32" ? "python" : "python3"),
    gateway: path.join(raizPdv, "wa-gateway", "dist", "index.js"),
    web: path.join(raizPdv, "web", "dist"),
    node: process.env.PDV_NODE || execPath,
    nodeEhElectron: Boolean(process.versions.electron),
  };
}

function urlSqlite(arquivo) {
  return `sqlite:///${path.resolve(arquivo).replace(/\\/g, "/")}`;
}

class Orquestrador extends EventEmitter {
  /**
   * @param {object} o
   * @param {string} o.dirDados pasta de dados do usuário (%APPDATA%\PDV Restaurantes)
   * @param {ReturnType<typeof caminhosRecursos>} o.caminhos
   * @param {number} [o.portaPainel]
   * @param {string} [o.hostPainel] "0.0.0.0" para a rede local; "127.0.0.1" só nesta máquina
   * @param {object} [o.opcoesServico] repassadas ao Servico (testes)
   */
  constructor({ dirDados, caminhos, portaPainel = PORTA_PAINEL, hostPainel = "0.0.0.0", opcoesServico = {} }) {
    super();
    this.dirDados = dirDados;
    this.caminhos = caminhos;
    this.portaPreferida = portaPainel;
    this.hostPainel = hostPainel;
    this.opcoesServico = opcoesServico;
    this.banco = path.join(dirDados, "pdv.sqlite");
    this.dirBackups = path.join(dirDados, "backups");
    this.dirLogs = path.join(dirDados, "logs");
    this.servicos = {};
    this.painel = null;
    this.info = null;
  }

  _envPython() {
    return {
      PYTHONPATH: this.caminhos.api,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    };
  }

  /** Executa `python -m pdv_api.ferramentas ...` e devolve o JSON da última linha. */
  ferramenta(args, timeoutMs = 120_000, envExtra = {}) {
    return new Promise((resolve, reject) => {
      childProcess.execFile(
        this.caminhos.python,
        ["-m", "pdv_api.ferramentas", ...args],
        { cwd: this.caminhos.api, env: { ...process.env, ...this._envPython(), ...envExtra }, timeout: timeoutMs, windowsHide: true },
        (erro, stdout) => {
          const linhas = String(stdout || "").trim().split(/\r?\n/);
          let saida = null;
          try {
            saida = JSON.parse(linhas[linhas.length - 1]);
          } catch {
            /* sem JSON */
          }
          if (saida && saida.ok) return resolve(saida);
          reject(new Error(saida?.erro || (erro ? `ferramenta falhou: ${erro.message}` : "ferramenta sem resposta")));
        },
      );
    });
  }

  async iniciar() {
    fs.mkdirSync(this.dirDados, { recursive: true });
    const segredos = carregarSegredos(this.dirDados);
    const portaApi = await escolherPorta(0);
    const portaGateway = await escolherPorta(0);
    const hostTeste = this.hostPainel === "0.0.0.0" ? undefined : this.hostPainel;
    const portaPainel = await escolherPorta(this.portaPreferida, hostTeste);
    const ip = this.hostPainel === "0.0.0.0" ? enderecoLocal() : null;
    const enderecoRede = ip ? `http://${ip}:${portaPainel}` : "";

    this.emit("etapa", "Preparando o banco de dados");
    await this.ferramenta(["migrar", "--banco", this.banco]);

    const api = new Servico({
      nome: "api",
      comando: this.caminhos.python,
      args: [
        "-m", "uvicorn", "pdv_api.main:criar_app_do_ambiente", "--factory",
        "--host", "127.0.0.1", "--port", String(portaApi), "--proxy-headers", "--no-access-log",
      ],
      cwd: this.caminhos.api,
      env: {
        ...this._envPython(),
        DATABASE_URL: urlSqlite(this.banco),
        JWT_SECRET: segredos.jwtSecret,
        GATEWAY_TOKEN: segredos.gatewayToken,
        GATEWAY_URL: `http://127.0.0.1:${portaGateway}`,
        PDV_RESTAURANTE_UNICO: "1",
        PDV_ENDERECO_REDE: enderecoRede,
        // Só o servidor do painel, nesta máquina, informa o IP do cliente (REV-07, REV-19)
        FORWARDED_ALLOW_IPS: "127.0.0.1",
        PDV_VIGIAR_PAI: "1",
      },
      urlSaude: `http://127.0.0.1:${portaApi}/saude`,
      arquivoLog: path.join(this.dirLogs, "api.log"),
      ...this.opcoesServico,
    });
    const gateway = new Servico({
      nome: "whatsapp",
      comando: this.caminhos.node,
      args: [this.caminhos.gateway],
      cwd: path.dirname(path.dirname(this.caminhos.gateway)),
      env: {
        ...(this.caminhos.nodeEhElectron ? { ELECTRON_RUN_AS_NODE: "1" } : {}),
        NODE_ENV: "production",
        GATEWAY_TOKEN: segredos.gatewayToken,
        API_URL: `http://127.0.0.1:${portaApi}`,
        DATA_DIR: path.join(this.dirDados, "whatsapp"),
        PORT: String(portaGateway),
        HOST: "127.0.0.1",
        PDV_VIGIAR_PAI: "1",
      },
      urlSaude: `http://127.0.0.1:${portaGateway}/saude`,
      arquivoLog: path.join(this.dirLogs, "whatsapp.log"),
      ...this.opcoesServico,
    });
    for (const s of [api, gateway]) {
      s.on("estado", (e) => this.emit("estado", e));
      s.on("falhou", (e) => this.emit("falhou", e));
    }
    this.servicos = { api, gateway };

    this.emit("etapa", "Iniciando o sistema");
    api.iniciar();
    await api.aguardarSaude();
    this.emit("etapa", "Conectando o WhatsApp");
    gateway.iniciar();
    await gateway.aguardarSaude();

    this.painel = criarServidorPainel({ raiz: this.caminhos.web, apiPorta: portaApi });
    await new Promise((resolve, reject) => {
      this.painel.once("error", reject);
      this.painel.listen(portaPainel, this.hostPainel, resolve);
    });

    this.info = {
      portaApi,
      portaGateway,
      portaPainel,
      urlLocal: `http://127.0.0.1:${portaPainel}`,
      enderecoRede: enderecoRede || null,
      gatewayToken: segredos.gatewayToken,
    };
    // Para suporte e testes: onde cada peça está ouvindo (sem segredos; esses ficam em segredos.json)
    fs.writeFileSync(
      path.join(this.dirDados, "instancia.json"),
      JSON.stringify({ pid: process.pid, portaApi, portaGateway, portaPainel, urlLocal: this.info.urlLocal, enderecoRede: this.info.enderecoRede }, null, 2),
    );
    this.emit("pronto", this.info);
    return this.info;
  }

  /** Status do WhatsApp pela API (RF-26): [{restaurante, status}]. */
  conexoes() {
    if (!this.info) return Promise.resolve([]);
    return new Promise((resolve) => {
      const req = http.get(
        `http://127.0.0.1:${this.info.portaApi}/canal/conexoes`,
        { headers: { "X-Gateway-Token": this.info.gatewayToken }, timeout: 5000 },
        (res) => {
          let corpo = "";
          res.on("data", (d) => (corpo += d));
          res.on("end", () => {
            try {
              resolve(res.statusCode === 200 ? JSON.parse(corpo) : []);
            } catch {
              resolve([]);
            }
          });
        },
      );
      req.on("timeout", () => req.destroy());
      req.on("error", () => resolve([]));
    });
  }

  backup(motivo = "manual", manter = 14) {
    return this.ferramenta(["backup", "--banco", this.banco, "--destino", this.dirBackups, "--manter", String(manter), "--motivo", motivo]);
  }

  /** Último backup automático diário, para decidir se é hora de outro. */
  ultimoBackup() {
    try {
      const nomes = fs.readdirSync(this.dirBackups).filter((n) => /^pdv-\d{8}-\d{6}-.*\.sqlite$/.test(n)).sort();
      if (!nomes.length) return null;
      const m = /^pdv-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(nomes[nomes.length - 1]);
      return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    } catch {
      return null;
    }
  }

  /** Senha do dono esquecida (RF-28). A senha vai por variável de ambiente, nunca na linha de comando. */
  redefinirSenha(email, senha) {
    return this.ferramenta(["redefinir-senha", "--banco", this.banco, "--email", email], 60_000, { PDV_NOVA_SENHA: senha });
  }

  /** Para API e gateway, troca o banco pelo backup e sobe de novo. */
  async restaurar(arquivo) {
    const { api, gateway } = this.servicos;
    await gateway.parar();
    await api.parar();
    try {
      return await this.ferramenta(["restaurar", "--banco", this.banco, "--arquivo", arquivo]);
    } finally {
      api.zerarQuedas();
      gateway.zerarQuedas();
      api.iniciar();
      await api.aguardarSaude();
      gateway.iniciar();
      await gateway.aguardarSaude();
    }
  }

  async parar() {
    try {
      fs.rmSync(path.join(this.dirDados, "instancia.json"), { force: true });
    } catch {
      /* melhor esforço */
    }
    if (this.painel) {
      await new Promise((r) => this.painel.close(() => r()));
      this.painel.closeAllConnections?.();
      this.painel = null;
    }
    const { api, gateway } = this.servicos;
    if (gateway) await gateway.parar();
    if (api) await api.parar();
  }
}

module.exports = { Orquestrador, caminhosRecursos, urlSqlite, PORTA_PAINEL };
