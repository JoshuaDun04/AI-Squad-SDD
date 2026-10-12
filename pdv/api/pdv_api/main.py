"""Fábrica da aplicação. Em produção: uvicorn pdv_api.main:criar_app_do_ambiente --factory."""

from __future__ import annotations

import logging
import os
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from pdv_api.banco import criar_engine
from pdv_api.config import Config
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.dominio.lgpd import instalar_filtro
from pdv_api.erros import registrar_erro_interno, registrar_tratadores
from pdv_api.gateway_baileys import GatewayBaileys
from pdv_api.relogio import Relogio, RelogioSistema
from pdv_api.rotas import auth, canal, cardapio, horarios, pedidos, relatorio, usuarios, whatsapp


def criar_app(
    config: Config,
    canal_mensagens: CanalMensagens | None = None,
    relogio: Relogio | None = None,
    fabrica_sessao: sessionmaker | None = None,
) -> FastAPI:
    app = FastAPI(title="PDV Restaurantes — API", version="0.1.0")
    if fabrica_sessao is None:
        # hide_parameters: valores (telefone, endereço) nunca aparecem em mensagens de erro do SQLAlchemy
        engine = criar_engine(config.database_url)
        fabrica_sessao = sessionmaker(engine, expire_on_commit=False)
    app.state.fabrica_sessao = fabrica_sessao
    app.state.config = config
    app.state.relogio = relogio or RelogioSistema()
    app.state.canal = canal_mensagens or GatewayBaileys(config.gateway_url, config.gateway_token)

    if config.cors_origens:  # desligado por padrão (SEC-02)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origens),
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )

    registrar_tratadores(app)
    registrar_erro_interno(app)
    for r in (auth.router, usuarios.router, cardapio.router, horarios.router, whatsapp.router, pedidos.router, relatorio.router, canal.router):
        app.include_router(r)

    @app.get("/saude", tags=["infra"])
    def saude() -> dict:
        return {"ok": True}

    return app


def vigiar_processo_pai(entrada=None, sair=os._exit) -> threading.Thread:
    """App Windows (RT-19): o app segura a entrada padrão aberta; se ele morrer, a entrada fecha e a API sai.

    Evita uma API órfã segurando o banco depois de o app fechar à força.
    """

    def _vigiar() -> None:
        fluxo = entrada if entrada is not None else sys.stdin.buffer
        try:
            while fluxo.read(1024):
                pass
        except (OSError, ValueError):
            pass
        sair(0)

    t = threading.Thread(target=_vigiar, name="vigia-app", daemon=True)
    t.start()
    return t


def criar_app_do_ambiente() -> FastAPI:
    if os.environ.get("PDV_VIGIAR_PAI") == "1":
        vigiar_processo_pai()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for nome in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        instalar_filtro(logging.getLogger(nome))
    return criar_app(Config.do_ambiente())
