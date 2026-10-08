"""Horário de funcionamento (RF-05, RN-07).

dia_semana segue datetime.weekday(): 0 = segunda-feira ... 6 = domingo.
Uma faixa por dia; fecha > abre (sem virada de meia-noite na R1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

DIAS_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


@dataclass(frozen=True)
class Faixa:
    dia_semana: int
    abre: time
    fecha: time


def esta_aberto(faixas: list[Faixa], agora_local: datetime) -> bool:
    """Aberto quando abre <= hora < fecha no dia da semana local."""
    hora = agora_local.time().replace(tzinfo=None)
    dia = agora_local.weekday()
    return any(f.dia_semana == dia and f.abre <= hora < f.fecha for f in faixas)


def proxima_abertura(faixas: list[Faixa], agora_local: datetime) -> datetime | None:
    """Próximo instante de abertura estritamente depois de agora (até 7 dias)."""
    candidatos: list[datetime] = []
    for delta in range(0, 8):
        dia = (agora_local + timedelta(days=delta)).date()
        for f in faixas:
            if f.dia_semana != dia.weekday():
                continue
            inicio = datetime.combine(dia, f.abre, tzinfo=agora_local.tzinfo)
            if inicio > agora_local:
                candidatos.append(inicio)
        if candidatos:
            break
    return min(candidatos) if candidatos else None


def descrever_proxima_abertura(faixas: list[Faixa], agora_local: datetime) -> str:
    prox = proxima_abertura(faixas, agora_local)
    if prox is None:
        return "No momento não temos horário de funcionamento cadastrado."
    hora = prox.strftime("%H:%M")
    dias = (prox.date() - agora_local.date()).days
    if dias == 0:
        quando = f"hoje às {hora}"
    elif dias == 1:
        quando = f"amanhã às {hora}"
    else:
        quando = f"{DIAS_SEMANA[prox.weekday()]} às {hora}"
    return f"Abrimos {quando}."
