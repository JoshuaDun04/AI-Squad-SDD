"""Dinheiro em centavos inteiros (ADR-0004, RN-02).

A formatação "R$ 12,90" só acontece na borda: mensagens do robô e painel.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Valor máximo aceito em texto livre (troco): R$ 100.000,00
VALOR_MAXIMO_CENTAVOS = 10_000_000

_RE_VALOR = re.compile(
    r"^(?:r\$\s*)?(?P<inteiro>\d{1,3}(?:\.\d{3})+|\d+)(?:[.,](?P<centavos>\d{1,2}))?$",
    re.IGNORECASE,
)


def formatar_brl(centavos: int) -> str:
    """4590 -> "R$ 45,90"; 123456 -> "R$ 1.234,56"."""
    sinal = "-" if centavos < 0 else ""
    reais, cent = divmod(abs(centavos), 100)
    reais_fmt = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {reais_fmt},{cent:02d}"


def interpretar_valor_brl(texto: str) -> int | None:
    """Converte texto do cliente em centavos. "50" -> 5000, "50,5" -> 5050.

    Retorna None quando o texto não é um valor monetário válido.
    """
    limpo = texto.strip().replace(" ", "")
    m = _RE_VALOR.match(limpo)
    if not m:
        return None
    inteiro = int(m.group("inteiro").replace(".", ""))
    cent_txt = m.group("centavos") or "0"
    centavos = int(cent_txt) * (10 if len(cent_txt) == 1 else 1)
    valor = inteiro * 100 + centavos
    if valor <= 0 or valor > VALOR_MAXIMO_CENTAVOS:
        return None
    return valor


def total_centavos(linhas: Iterable[tuple[int, int]]) -> int:
    """Soma de preço unitário × quantidade, sem arredondamento."""
    return sum(preco * quantidade for preco, quantidade in linhas)
