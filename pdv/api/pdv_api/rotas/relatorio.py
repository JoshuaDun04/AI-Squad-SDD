"""RF-27 relatório do piloto no painel (só admin; sem dados pessoais)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pdv_api.dependencias import exigir, obter_relogio, obter_sessao
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoConexao, RepoPedidos, RepoRestaurantes
from pdv_api.seguranca import Principal
from pdv_api.servicos import relatorio
from pdv_api.servicos.comum import agora_local

router = APIRouter(tags=["relatório"])


@router.get("/relatorio")
def relatorio_piloto(
    dias: int = Query(default=7, ge=1, le=366),
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
) -> dict:
    restaurante = RepoRestaurantes(sessao).obter(p.restaurante_id)
    hoje = agora_local(restaurante, relogio.agora()).date()
    repo = RepoPedidos(sessao, p.restaurante_id)
    pedidos = repo.desde(hoje - timedelta(days=dias - 1))
    linhas = repo.itens_de([x.id for x in pedidos if x.status != "Cancelado"])
    dados = relatorio.montar(
        [
            relatorio.PedidoRel(
                x.data_local, x.status, x.tipo, x.total_centavos, x.motivo_cancelamento,
                x.criado_em, x.em_preparo_em, x.pronto_em, x.finalizado_em,
            )
            for x in pedidos
        ],
        ((i.nome, i.quantidade) for lista in linhas.values() for i in lista),
        restaurante.fuso,
        dias,
    )
    conexao = RepoConexao(sessao, p.restaurante_id).obter()
    dados["whatsapp"] = conexao.status if conexao else "desconectado"
    dados["ate"] = hoje.isoformat()
    return dados
