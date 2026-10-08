"""RF-09 fila da cozinha, RF-10 status, RF-11 cancelamento, histórico do dia."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dependencias import TODOS, exigir, obter_canal, obter_relogio, obter_sessao
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.erros import nao_encontrado
from pdv_api.relogio import Relogio, em_utc
from pdv_api.repositorios import RepoConversas, RepoPedidos, RepoRestaurantes
from pdv_api.seguranca import Principal
from pdv_api.servicos import pedidos as servico
from pdv_api.servicos.comum import agora_local

router = APIRouter(tags=["pedidos"])


class NovoStatus(BaseModel):
    novo_status: str = Field(max_length=20)


class Cancelamento(BaseModel):
    motivo: str = Field(default="", max_length=300)


def _resumo(p: m.Pedido, itens: list[m.PedidoItem]) -> dict:
    """Visão da cozinha: sem endereço, sem telefone (RN-10)."""
    return {
        "pedido_id": str(p.id),
        "numero": p.numero,
        "status": p.status,
        "criado_em": em_utc(p.criado_em).isoformat(),
        "tipo": p.tipo,
        "observacao": p.observacao,
        "itens": [{"nome": i.nome, "quantidade": i.quantidade} for i in itens],
    }


@router.get("/fila")
def fila(p: Principal = Depends(exigir(*TODOS)), sessao: Session = Depends(obter_sessao)) -> list[dict]:
    repo = RepoPedidos(sessao, p.restaurante_id)
    pedidos = repo.fila()
    itens = repo.itens_de([x.id for x in pedidos])
    return [_resumo(x, itens.get(x.id, [])) for x in pedidos]


@router.get("/pedidos")
def historico(
    data: date | None = None,
    p: Principal = Depends(exigir("atendente", "admin")),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
) -> list[dict]:
    if data is None:
        restaurante = RepoRestaurantes(sessao).obter(p.restaurante_id)
        data = agora_local(restaurante, relogio.agora()).date()
    repo = RepoPedidos(sessao, p.restaurante_id)
    pedidos = repo.do_dia(data)
    itens = repo.itens_de([x.id for x in pedidos])
    return [
        {**_resumo(x, itens.get(x.id, [])), "total_centavos": x.total_centavos, "pagamento": x.pagamento}
        for x in pedidos
    ]


@router.get("/pedidos/{pedido_id}")
def detalhe(
    pedido_id: uuid.UUID, p: Principal = Depends(exigir("atendente", "admin")), sessao: Session = Depends(obter_sessao)
) -> dict:
    repo = RepoPedidos(sessao, p.restaurante_id)
    pedido = repo.obter(pedido_id)
    if pedido is None:
        raise nao_encontrado("pedido")
    cliente = RepoConversas(sessao, p.restaurante_id).obter_cliente(pedido.cliente_id)
    return {
        "pedido_id": str(pedido.id),
        "numero": pedido.numero,
        "data_local": pedido.data_local.isoformat(),
        "status": pedido.status,
        "tipo": pedido.tipo,
        "endereco": pedido.endereco,
        "pagamento": pedido.pagamento,
        "troco_para_centavos": pedido.troco_para_centavos,
        "total_centavos": pedido.total_centavos,
        "motivo_cancelamento": pedido.motivo_cancelamento,
        "observacao": pedido.observacao,
        "criado_em": em_utc(pedido.criado_em).isoformat(),
        "cliente": {"nome_perfil": cliente.nome_perfil, "telefone": cliente.telefone} if cliente else None,
        "itens": [
            {
                "item_id": str(i.item_id),
                "nome": i.nome,
                "preco_unitario_centavos": i.preco_unitario_centavos,
                "quantidade": i.quantidade,
            }
            for i in repo.itens(pedido.id)
        ],
    }


@router.post("/pedidos/{pedido_id}/status")
def mudar_status(
    pedido_id: uuid.UUID,
    dados: NovoStatus,
    p: Principal = Depends(exigir(*TODOS)),
    sessao: Session = Depends(obter_sessao),
    canal: CanalMensagens = Depends(obter_canal),
) -> dict:
    pedido = servico.mudar_status(sessao, p.restaurante_id, pedido_id, dados.novo_status, canal)
    return {"status": pedido.status}


@router.post("/pedidos/{pedido_id}/cancelar")
def cancelar(
    pedido_id: uuid.UUID,
    dados: Cancelamento,
    p: Principal = Depends(exigir("atendente", "admin")),
    sessao: Session = Depends(obter_sessao),
    canal: CanalMensagens = Depends(obter_canal),
) -> dict:
    pedido = servico.cancelar(sessao, p.restaurante_id, pedido_id, dados.motivo, canal)
    return {"status": pedido.status, "motivo": pedido.motivo_cancelamento}
