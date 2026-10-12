"""Relatório do piloto (RF-27, DEC-10). Sem dados pessoais: nada de telefone, nome ou endereço."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pdv_api.relogio import em_utc

ABERTOS = {"Recebido", "Em preparo", "Pronto"}


@dataclass(frozen=True)
class PedidoRel:
    data_local: date
    status: str
    tipo: str
    total_centavos: int
    motivo_cancelamento: str | None
    criado_em: datetime
    em_preparo_em: datetime | None
    pronto_em: datetime | None
    finalizado_em: datetime | None


def percentil(valores: list[float], p: float) -> float | None:
    """Interpolação linear, igual ao percentile_cont do PostgreSQL."""
    if not valores:
        return None
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * p
    baixo, alto = math.floor(posicao), math.ceil(posicao)
    if baixo == alto:
        return ordenados[baixo]
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (posicao - baixo)


def _minutos(inicio: datetime | None, fim: datetime | None) -> float | None:
    if inicio is None or fim is None:
        return None
    return (em_utc(fim) - em_utc(inicio)).total_seconds() / 60


def _resumo_tempo(valores: list[float]) -> dict:
    def arred(v: float | None) -> float | None:
        return None if v is None else round(v, 1)

    return {"pedidos": len(valores), "mediana_min": arred(percentil(valores, 0.5)), "p90_min": arred(percentil(valores, 0.9))}


def montar(pedidos: list[PedidoRel], itens: Iterable[tuple[str, int]], fuso: str, dias: int) -> dict:
    """`itens`: (nome, quantidade) das linhas de pedidos não cancelados do período."""
    zona = ZoneInfo(fuso)
    por_dia: dict[date, list[PedidoRel]] = defaultdict(list)
    for p in pedidos:
        por_dia[p.data_local].append(p)

    linhas_dia = []
    for dia in sorted(por_dia):
        lista = por_dia[dia]
        validos = [p for p in lista if p.status != "Cancelado"]
        linhas_dia.append(
            {
                "dia": dia.isoformat(),
                "pedidos": len(lista),
                "finalizados": sum(p.status == "Finalizado" for p in lista),
                "cancelados": sum(p.status == "Cancelado" for p in lista),
                "em_aberto": sum(p.status in ABERTOS for p in lista),
                "entregas": sum(p.tipo == "entrega" for p in lista),
                "ticket_medio_centavos": round(sum(p.total_centavos for p in validos) / len(validos)) if validos else None,
                "vendido_centavos": sum(p.total_centavos for p in validos),
            }
        )

    ate_preparo = [m for p in pedidos if (m := _minutos(p.criado_em, p.em_preparo_em)) is not None]
    preparo = [m for p in pedidos if (m := _minutos(p.em_preparo_em, p.pronto_em)) is not None]
    pronto_final = [m for p in pedidos if (m := _minutos(p.pronto_em, p.finalizado_em)) is not None]

    horas = Counter(em_utc(p.criado_em).astimezone(zona).hour for p in pedidos)
    motivos = Counter(p.motivo_cancelamento or "(sem motivo)" for p in pedidos if p.status == "Cancelado")
    unidades: Counter[str] = Counter()
    for nome, qtd in itens:
        unidades[nome] += qtd

    validos = [p for p in pedidos if p.status != "Cancelado"]
    return {
        "dias": dias,
        "totais": {
            "pedidos": len(pedidos),
            "cancelados": sum(p.status == "Cancelado" for p in pedidos),
            "vendido_centavos": sum(p.total_centavos for p in validos),
            "ticket_medio_centavos": round(sum(p.total_centavos for p in validos) / len(validos)) if validos else None,
        },
        "por_dia": linhas_dia,
        "tempos": {
            "ate_preparo": _resumo_tempo(ate_preparo),
            "preparo": _resumo_tempo(preparo),
            "pronto_ate_finalizado": _resumo_tempo(pronto_final),
        },
        "por_hora": [{"hora": h, "pedidos": n} for h, n in sorted(horas.items())],
        "cancelamentos": [{"motivo": m, "vezes": n} for m, n in motivos.most_common()],
        "itens_mais_pedidos": [{"nome": n, "unidades": u} for n, u in unidades.most_common(10)],
    }
