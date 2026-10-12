"""Criação do engine do banco. No app Windows o banco é SQLite (ADR-0012)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

BUSY_TIMEOUT_MS = 5000


def _configurar_sqlite(engine: Engine, wal: bool) -> None:
    @event.listens_for(engine, "connect")
    def _ao_conectar(conexao_dbapi: Any, _registro: Any) -> None:
        # Desliga a transação implícita do pysqlite: o BEGIN é emitido abaixo
        conexao_dbapi.isolation_level = None
        cursor = conexao_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        if wal:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _ao_comecar(conexao: Any) -> None:
        # Escritas em série: substitui SELECT ... FOR UPDATE e SKIP LOCKED do PostgreSQL
        conexao.exec_driver_sql("BEGIN IMMEDIATE")


def criar_engine(url: str, **opcoes: Any) -> Engine:
    """Engine com hide_parameters (RN-10) e, no SQLite, WAL + foreign keys + BEGIN IMMEDIATE."""
    opcoes.setdefault("hide_parameters", True)
    if not url.startswith("sqlite"):
        opcoes.setdefault("pool_pre_ping", True)
        return create_engine(url, **opcoes)
    em_memoria = url in ("sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:", "sqlite+pysqlite://")
    opcoes.setdefault("connect_args", {"check_same_thread": False})
    if em_memoria:
        opcoes.setdefault("poolclass", StaticPool)
    engine = create_engine(url, **opcoes)
    _configurar_sqlite(engine, wal=not em_memoria)
    return engine
