"""Webhook do gateway WhatsApp (RT-03): mensagens recebidas e status da conexão."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pdv_api.dependencias import obter_canal, obter_relogio, obter_sessao, token_gateway_valido
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.erros import nao_encontrado
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoConexao, RepoRestaurantes
from pdv_api.servicos.robo_servico import MensagemRecebida, RestauranteInexistente, processar_mensagem

router = APIRouter(prefix="/canal", tags=["canal"], dependencies=[Depends(token_gateway_valido)])


class EventoMensagem(BaseModel):
    tipo: Literal["mensagem"]
    restaurante_id: uuid.UUID
    mensagem_id: str = Field(min_length=1, max_length=128)
    telefone: str = Field(pattern=r"^\d{8,15}$")
    nome_perfil: str = Field(default="", max_length=120)
    texto: str = Field(default="", max_length=2000)
    recebida_em: str | None = None


class EventoConexao(BaseModel):
    tipo: Literal["status_conexao"]
    restaurante_id: uuid.UUID
    status: Literal["aguardando_qr", "conectado", "desconectado"]
    qr_code: str | None = Field(default=None, max_length=20000)


Evento = Annotated[EventoMensagem | EventoConexao, Field(discriminator="tipo")]


@router.post("/webhook")
def webhook(
    evento: Evento,
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
    canal: CanalMensagens = Depends(obter_canal),
) -> dict:
    if isinstance(evento, EventoConexao):
        if RepoRestaurantes(sessao).obter(evento.restaurante_id) is None:
            raise nao_encontrado("restaurante")
        RepoConexao(sessao, evento.restaurante_id).definir(evento.status, evento.qr_code, relogio.agora())
        sessao.commit()
        return {"ok": True}

    try:
        processar_mensagem(
            sessao,
            MensagemRecebida(
                restaurante_id=evento.restaurante_id,
                mensagem_id=evento.mensagem_id,
                telefone=evento.telefone,
                nome_perfil=evento.nome_perfil,
                texto=evento.texto,
            ),
            relogio,
            canal,
        )
    except RestauranteInexistente as exc:
        raise nao_encontrado("restaurante") from exc
    return {"ok": True}
