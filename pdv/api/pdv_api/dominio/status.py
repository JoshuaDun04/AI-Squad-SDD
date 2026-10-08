"""Status do pedido e transições permitidas (RN-09)."""

from __future__ import annotations

from enum import StrEnum

from pdv_api.dominio.dinheiro import formatar_brl


class StatusPedido(StrEnum):
    RECEBIDO = "Recebido"
    EM_PREPARO = "Em preparo"
    PRONTO = "Pronto"
    FINALIZADO = "Finalizado"
    CANCELADO = "Cancelado"


_PROXIMO: dict[StatusPedido, StatusPedido] = {
    StatusPedido.RECEBIDO: StatusPedido.EM_PREPARO,
    StatusPedido.EM_PREPARO: StatusPedido.PRONTO,
    StatusPedido.PRONTO: StatusPedido.FINALIZADO,
}

_CANCELAVEIS = frozenset({StatusPedido.RECEBIDO, StatusPedido.EM_PREPARO})

# Fila da cozinha: pedidos ainda não finalizados nem cancelados
STATUS_NA_FILA: tuple[StatusPedido, ...] = (
    StatusPedido.RECEBIDO,
    StatusPedido.EM_PREPARO,
    StatusPedido.PRONTO,
)


def pode_avancar(atual: StatusPedido, novo: StatusPedido) -> bool:
    """Só avança um passo na ordem; nunca pula nem volta."""
    return _PROXIMO.get(atual) == novo


def pode_cancelar(atual: StatusPedido) -> bool:
    return atual in _CANCELAVEIS


def mensagem_status(numero: int, status: StatusPedido, tipo: str, motivo: str | None = None) -> str:
    """Aviso enviado ao cliente a cada mudança de status (RF-10, RF-11)."""
    if status is StatusPedido.EM_PREPARO:
        return f"Seu pedido #{numero} está em preparo."
    if status is StatusPedido.PRONTO:
        if tipo == "entrega":
            return f"Seu pedido #{numero} está pronto e vai sair para entrega."
        return f"Seu pedido #{numero} está pronto! Pode vir retirar."
    if status is StatusPedido.FINALIZADO:
        return f"Pedido #{numero} finalizado. Obrigado pela preferência!"
    if status is StatusPedido.CANCELADO:
        return f"Seu pedido #{numero} foi cancelado. Motivo: {motivo}"
    return f"Pedido #{numero}: {status.value}."


def mensagem_pedido_recebido(numero: int, total: int) -> str:
    return f"Pedido #{numero} recebido! Total {formatar_brl(total)}"
