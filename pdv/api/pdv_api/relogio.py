"""Relógio injetável: o domínio nunca chama datetime.now() direto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Relogio(Protocol):
    def agora(self) -> datetime: ...


class RelogioSistema:
    def agora(self) -> datetime:
        return datetime.now(UTC)


class RelogioFixo:
    """Para testes: hora controlada. Sempre devolve UTC, como o relógio do sistema."""

    def __init__(self, inicio: datetime) -> None:
        if inicio.tzinfo is None:
            raise ValueError("RelogioFixo exige datetime com fuso")
        self._agora = inicio

    def agora(self) -> datetime:
        return self._agora.astimezone(UTC)

    def definir(self, momento: datetime) -> None:
        if momento.tzinfo is None:
            raise ValueError("datetime precisa ter fuso")
        self._agora = momento

    def avancar(self, **kwargs: float) -> None:
        self._agora += timedelta(**kwargs)


def em_utc(momento: datetime) -> datetime:
    """Normaliza datetimes vindos do banco (SQLite devolve sem fuso)."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)
