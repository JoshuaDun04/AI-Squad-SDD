"use strict";
/**
 * Supervisão de processos filhos (RT-19): reinicia com espera crescente e desiste depois de
 * muitas quedas seguidas, avisando o app (BDD-APP-02, BDD-APP-03).
 */
const childProcess = require("node:child_process");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const ATRASOS_PADRAO = [1000, 2000, 4000, 8000, 16000, 30000];
const LOG_MAXIMO = 5 * 1024 * 1024;

function obterSaude(url, timeout = 2000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("timeout", () => req.destroy());
    req.on("error", () => resolve(false));
  });
}

class Servico extends EventEmitter {
  /**
   * @param {object} o
   * @param {string} o.nome
   * @param {string} o.comando
   * @param {string[]} o.args
   * @param {Record<string,string>} [o.env]
   * @param {string} [o.cwd]
   * @param {string} [o.urlSaude] GET que responde 200 quando o serviço está pronto
   * @param {string} [o.arquivoLog]
   * @param {number[]} [o.atrasos]
   * @param {number} [o.maxFalhas] quedas dentro da janela até desistir
   * @param {number} [o.janelaMs]
   */
  constructor(o) {
    super();
    this.nome = o.nome;
    this.comando = o.comando;
    this.args = o.args;
    this.env = o.env || {};
    this.cwd = o.cwd;
    this.urlSaude = o.urlSaude;
    this.arquivoLog = o.arquivoLog;
    this.atrasos = o.atrasos || ATRASOS_PADRAO;
    this.maxFalhas = o.maxFalhas ?? 6;
    this.janelaMs = o.janelaMs ?? 10 * 60 * 1000;
    this.estado = "parado";
    this.processo = null;
    this.quedas = [];
    this.temporizador = null;
    this.parando = false;
  }

  _mudar(estado, detalhe) {
    if (this.estado === estado) return;
    this.estado = estado;
    this.emit("estado", { servico: this.nome, estado, detalhe });
  }

  _log(texto) {
    if (!this.arquivoLog) return;
    try {
      fs.mkdirSync(path.dirname(this.arquivoLog), { recursive: true });
      if (fs.existsSync(this.arquivoLog) && fs.statSync(this.arquivoLog).size > LOG_MAXIMO) {
        fs.renameSync(this.arquivoLog, `${this.arquivoLog}.1`);
      }
      fs.appendFileSync(this.arquivoLog, texto);
    } catch {
      /* log é melhor esforço */
    }
  }

  iniciar() {
    this.parando = false;
    clearTimeout(this.temporizador);
    this._mudar("iniciando");
    this._log(`--- ${new Date().toISOString()} iniciando ${this.nome}\n`);
    const filho = childProcess.spawn(this.comando, this.args, {
      cwd: this.cwd,
      env: { ...process.env, ...this.env },
      // Entrada em pipe: se o app morrer, ela fecha e o filho sai (PDV_VIGIAR_PAI)
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.processo = filho;
    filho.stdout.on("data", (d) => this._log(d.toString()));
    filho.stderr.on("data", (d) => this._log(d.toString()));
    filho.stdin.on("error", () => {});
    filho.on("error", (erro) => this._log(`erro ao iniciar: ${erro.message}\n`));
    filho.on("exit", (codigo, sinal) => {
      if (this.processo !== filho) return;
      this.processo = null;
      this._log(`--- ${this.nome} saiu (código ${codigo}, sinal ${sinal})\n`);
      if (this.parando) return this._mudar("parado");
      this._agendarReinicio(codigo);
    });
    if (!this.urlSaude) this._mudar("rodando");
    return filho;
  }

  _agendarReinicio(codigo) {
    const agora = Date.now();
    this.quedas = this.quedas.filter((t) => agora - t < this.janelaMs);
    this.quedas.push(agora);
    if (this.quedas.length > this.maxFalhas) {
      this._mudar("falhou", `caiu ${this.quedas.length} vezes em pouco tempo (último código ${codigo})`);
      this.emit("falhou", { servico: this.nome });
      return;
    }
    const atraso = this.atrasos[Math.min(this.quedas.length - 1, this.atrasos.length - 1)];
    this._mudar("reiniciando", `reinício em ${Math.round(atraso / 1000)} s`);
    this.temporizador = setTimeout(() => {
      this.iniciar();
      if (this.urlSaude) this.aguardarSaude().catch(() => {});
    }, atraso);
  }

  /** Espera o GET de saúde responder 200; marca "rodando". */
  async aguardarSaude(timeoutMs = 60_000, intervaloMs = 250) {
    if (!this.urlSaude) return true;
    const limite = Date.now() + timeoutMs;
    while (Date.now() < limite) {
      if (!this.processo) throw new Error(`${this.nome} terminou antes de ficar pronto`);
      if (await obterSaude(this.urlSaude)) {
        this._mudar("rodando");
        return true;
      }
      await new Promise((r) => setTimeout(r, intervaloMs));
    }
    throw new Error(`${this.nome} não respondeu em ${Math.round(timeoutMs / 1000)} s`);
  }

  /** Para o processo; no Windows encerra a árvore (taskkill /T). */
  parar(timeoutMs = 5000) {
    this.parando = true;
    clearTimeout(this.temporizador);
    const filho = this.processo;
    if (!filho) {
      this._mudar("parado");
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      const fim = setTimeout(() => {
        try {
          filho.kill("SIGKILL");
        } catch {
          /* já saiu */
        }
      }, timeoutMs);
      filho.once("exit", () => {
        clearTimeout(fim);
        resolve();
      });
      if (process.platform === "win32" && filho.pid) {
        childProcess.spawn("taskkill", ["/pid", String(filho.pid), "/T", "/F"], { windowsHide: true });
      } else {
        filho.kill("SIGTERM");
      }
    });
  }

  /** Recomeça a contagem de quedas (ex.: depois de o dono pedir "tentar de novo"). */
  zerarQuedas() {
    this.quedas = [];
  }
}

module.exports = { Servico, obterSaude };
