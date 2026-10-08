/** Servidor HTTP do gateway (API → gateway). Autenticado por X-Gateway-Token. */

import { timingSafeEqual } from "node:crypto";

import express, { type NextFunction, type Request, type Response } from "express";

export interface Sessoes {
  iniciar(restauranteId: string): Promise<void>;
  encerrar(restauranteId: string): Promise<void>;
  enviar(restauranteId: string, telefone: string, texto: string): Promise<void>;
}

/** Sessão inexistente ou ainda não conectada. */
export class SessaoIndisponivel extends Error {}

const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function tokenConfere(recebido: unknown, esperado: string): boolean {
  if (typeof recebido !== "string") return false;
  const a = Buffer.from(recebido);
  const b = Buffer.from(esperado);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function criarApp(sessoes: Sessoes, token: string): express.Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "32kb" }));

  app.get("/saude", (_req, res) => {
    res.json({ ok: true });
  });

  app.use((req: Request, res: Response, next: NextFunction) => {
    if (!tokenConfere(req.header("X-Gateway-Token"), token)) {
      res.status(401).json({ erro: "nao_autenticado" });
      return;
    }
    next();
  });

  const validarId = (req: Request, res: Response): string | null => {
    const id = String(req.params.restauranteId ?? "");
    if (!RE_UUID.test(id)) {
      res.status(400).json({ erro: "restaurante_invalido" });
      return null;
    }
    return id.toLowerCase();
  };

  app.post("/sessoes/:restauranteId", async (req, res) => {
    const id = validarId(req, res);
    if (!id) return;
    await sessoes.iniciar(id);
    res.status(202).json({ status: "aguardando_qr" });
  });

  app.delete("/sessoes/:restauranteId", async (req, res) => {
    const id = validarId(req, res);
    if (!id) return;
    await sessoes.encerrar(id);
    res.json({ status: "desconectado" });
  });

  app.post("/mensagens", async (req, res) => {
    const { restaurante_id, telefone, texto } = req.body ?? {};
    if (
      typeof restaurante_id !== "string" ||
      !RE_UUID.test(restaurante_id) ||
      typeof telefone !== "string" ||
      !/^\d{8,15}$/.test(telefone) ||
      typeof texto !== "string" ||
      texto.length === 0 ||
      texto.length > 4096
    ) {
      res.status(400).json({ erro: "corpo_invalido" });
      return;
    }
    try {
      await sessoes.enviar(restaurante_id.toLowerCase(), telefone, texto);
      res.json({ ok: true });
    } catch (erro) {
      if (erro instanceof SessaoIndisponivel) {
        res.status(409).json({ erro: "sessao_indisponivel" });
        return;
      }
      throw erro;
    }
  });

  // Erros não tratados: resposta genérica, sem vazar corpo (telefone/texto) para o log
  app.use((erro: Error & { type?: string; status?: number }, _req: Request, res: Response, _next: NextFunction) => {
    if (erro.type === "entity.parse.failed" || erro.type === "entity.too.large") {
      res.status(erro.status ?? 400).json({ erro: "corpo_invalido" }); // REV-12
      return;
    }
    console.error(`erro interno: ${erro.name}`);
    res.status(500).json({ erro: "interno" });
  });

  return app;
}
