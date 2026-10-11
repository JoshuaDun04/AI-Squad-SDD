"""Mudança de status e cancelamento com aviso ao cliente (RF-10, RF-11, RN-09)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.dominio.status import StatusPedido, mensagem_status, pode_avancar, pode_cancelar
from pdv_api.erros import ErroApi, nao_encontrado
from pdv_api.repositorios import RepoConversas, RepoPedidos
from pdv_api.servicos.comum import enviar_sem_falhar

MOTIVO_MIN = 3
MOTIVO_MAX = 300

_COLUNA_HORA = {
    StatusPedido.EM_PREPARO: "em_preparo_em",
    StatusPedido.PRONTO: "pronto_em",
    StatusPedido.FINALIZADO: "finalizado_em",
}


def _avisar(sessao: Session, canal: CanalMensagens, pedido: m.Pedido, texto: str) -> None:
    cliente = RepoConversas(sessao, pedido.restaurante_id).obter_cliente(pedido.cliente_id)
    if cliente is not None:
        enviar_sem_falhar(canal, pedido.restaurante_id, cliente.telefone, texto)


def mudar_status(
    sessao: Session,
    restaurante_id: uuid.UUID,
    pedido_id: uuid.UUID,
    novo: str,
    canal: CanalMensagens,
    agora: datetime,
) -> m.Pedido:
    pedido = RepoPedidos(sessao, restaurante_id).obter(pedido_id, para_atualizar=True)
    if pedido is None:
        raise nao_encontrado("pedido")
    try:
        novo_status = StatusPedido(novo)
    except ValueError as exc:
        raise ErroApi(422, "status_invalido", f"status desconhecido: {novo}") from exc
    if novo_status is StatusPedido.CANCELADO:
        raise ErroApi(422, "use_cancelar", "para cancelar use POST /pedidos/{id}/cancelar com motivo")
    atual = StatusPedido(pedido.status)
    if not pode_avancar(atual, novo_status):
        raise ErroApi(409, "transicao_invalida", f"não é possível ir de {atual.value} para {novo_status.value}")
    pedido.status = novo_status.value
    setattr(pedido, _COLUNA_HORA[novo_status], agora)
    sessao.commit()
    _avisar(sessao, canal, pedido, mensagem_status(pedido.numero, novo_status, pedido.tipo))
    return pedido


def cancelar(
    sessao: Session,
    restaurante_id: uuid.UUID,
    pedido_id: uuid.UUID,
    motivo: str,
    canal: CanalMensagens,
    agora: datetime,
) -> m.Pedido:
    pedido = RepoPedidos(sessao, restaurante_id).obter(pedido_id, para_atualizar=True)
    if pedido is None:
        raise nao_encontrado("pedido")
    motivo = " ".join((motivo or "").split())
    if not MOTIVO_MIN <= len(motivo) <= MOTIVO_MAX:
        raise ErroApi(422, "motivo_obrigatorio", f"informe o motivo ({MOTIVO_MIN} a {MOTIVO_MAX} caracteres)")
    atual = StatusPedido(pedido.status)
    if not pode_cancelar(atual):
        raise ErroApi(409, "transicao_invalida", f"pedido {atual.value} não pode ser cancelado")
    pedido.status = StatusPedido.CANCELADO.value
    pedido.motivo_cancelamento = motivo
    pedido.cancelado_em = agora
    sessao.commit()
    _avisar(sessao, canal, pedido, mensagem_status(pedido.numero, StatusPedido.CANCELADO, pedido.tipo, motivo))
    return pedido
