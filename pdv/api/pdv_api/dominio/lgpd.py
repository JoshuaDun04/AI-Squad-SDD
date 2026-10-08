"""LGPD mínima nos logs (RN-10, RT-06).

Regra principal: o código nunca loga endereço nem telefone completo; usa
mascarar_telefone(). O filtro abaixo é uma segunda barreira que mascara
qualquer sequência com cara de telefone que escape para um log.
"""

from __future__ import annotations

import logging
import re

# 10 a 15 dígitos: telefone com DDD (10-11), com país (12-13) ou identificador LID (14-15).
# Não encosta em letras, dígitos ou hífen, para não pegar trechos de UUID (REV-11);
# datas como 20261008 (8 dígitos) ficam legíveis (REV-21).
_RE_TELEFONE = re.compile(r"(?<![\w-])\+?\d{10,15}(?![\w-])")


def mascarar_telefone(telefone: str) -> str:
    """"5592991234567" -> "*****-4567"."""
    digitos = re.sub(r"\D", "", telefone or "")
    return f"*****-{digitos[-4:]}" if len(digitos) >= 4 else "*****"


def mascarar_texto(texto: str) -> str:
    return _RE_TELEFONE.sub(lambda m: mascarar_telefone(m.group(0)), texto)


class FiltroDadosPessoais(logging.Filter):
    """Mascara telefones na mensagem final do registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            mensagem = record.getMessage()
        except Exception:  # pragma: no cover - registro malformado
            return True
        mascarada = mascarar_texto(mensagem)
        if mascarada != mensagem:
            record.msg = mascarada
            record.args = None
        return True


def instalar_filtro(logger: logging.Logger | None = None) -> None:
    alvo = logger or logging.getLogger()
    if not any(isinstance(f, FiltroDadosPessoais) for f in alvo.filters):
        alvo.addFilter(FiltroDadosPessoais())
    for handler in alvo.handlers:
        if not any(isinstance(f, FiltroDadosPessoais) for f in handler.filters):
            handler.addFilter(FiltroDadosPessoais())
