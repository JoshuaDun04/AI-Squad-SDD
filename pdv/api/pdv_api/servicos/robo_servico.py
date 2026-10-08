"""Recebe a mensagem do gateway, roda a máquina de estados e cria o pedido."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dominio import robo
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.dominio.horario import descrever_proxima_abertura, esta_aberto
from pdv_api.dominio.lgpd import mascarar_telefone
from pdv_api.dominio.status import StatusPedido, mensagem_pedido_recebido
from pdv_api.relogio import Relogio, em_utc
from pdv_api.repositorios import RepoCardapio, RepoConversas, RepoHorarios, RepoPedidos, RepoRestaurantes
from pdv_api.servicos.comum import agora_local, enviar_sem_falhar, faixas

log = logging.getLogger("pdv_api.robo")

EXPIRACAO = timedelta(minutes=30)  # RN-06


@dataclass(frozen=True)
class MensagemRecebida:
    restaurante_id: uuid.UUID
    mensagem_id: str
    telefone: str
    nome_perfil: str
    texto: str


class RestauranteInexistente(Exception):
    pass


def montar_contexto(
    sessao: Session, restaurante: m.Restaurante, agora: datetime, ultima_msg_em: datetime | None
) -> robo.Contexto:
    rid = restaurante.id
    local = agora_local(restaurante, agora)
    fx = faixas(RepoHorarios(sessao, rid).listar())
    categorias = tuple(
        robo.CategoriaVista(
            id=str(cat.id),
            nome=cat.nome,
            itens=tuple(robo.ItemVista(str(it.id), it.nome, it.preco_centavos) for it in itens),
        )
        for cat, itens in RepoCardapio(sessao, rid).cardapio_disponivel()
    )
    expirou = ultima_msg_em is not None and agora - em_utc(ultima_msg_em) > EXPIRACAO
    return robo.Contexto(
        nome_restaurante=restaurante.nome,
        categorias=categorias,
        aberto=esta_aberto(fx, local),
        texto_proxima_abertura=descrever_proxima_abertura(fx, local),
        expirou=expirou,
    )


def processar_mensagem(
    sessao: Session, msg: MensagemRecebida, relogio: Relogio, canal: CanalMensagens
) -> m.Pedido | None:
    """Idempotente por mensagem_id (BDD-WA-04). Retorna o pedido criado, se houver."""
    restaurante = RepoRestaurantes(sessao).obter(msg.restaurante_id)
    if restaurante is None:
        raise RestauranteInexistente()
    rid = restaurante.id
    conversas = RepoConversas(sessao, rid)
    if conversas.mensagem_ja_processada(msg.mensagem_id):
        return None

    agora = relogio.agora()
    cliente = conversas.cliente(msg.telefone, msg.nome_perfil)
    conversa_db = conversas.conversa(cliente.id)
    ctx = montar_contexto(sessao, restaurante, agora, conversa_db.ultima_msg_em)
    estado = robo.Conversa(
        estado=robo.Estado(conversa_db.estado),
        carrinho=[dict(l) for l in (conversa_db.carrinho_json or [])],
        dados=dict(conversa_db.dados_json or {}),
    )
    resultado = robo.processar(estado, msg.texto, ctx)

    pedido = None
    respostas = list(resultado.respostas)
    if resultado.pedido is not None:
        pedido = _criar_pedido(sessao, restaurante, cliente.id, resultado.pedido, agora)
        respostas.append(mensagem_pedido_recebido(pedido.numero, pedido.total_centavos))

    conversa_db.estado = resultado.conversa.estado.value
    conversa_db.carrinho_json = resultado.conversa.carrinho
    conversa_db.dados_json = resultado.conversa.dados
    conversa_db.ultima_msg_em = agora
    conversas.marcar_processada(msg.mensagem_id)
    try:
        sessao.commit()
    except IntegrityError:
        # outra entrega da mesma mensagem ganhou a corrida: nada a fazer
        sessao.rollback()
        log.info("mensagem duplicada ignorada restaurante=%s", rid)
        return None

    if pedido is not None:
        log.info("pedido criado restaurante=%s numero=%s cliente=%s", rid, pedido.numero, mascarar_telefone(msg.telefone))
    if respostas:
        enviar_sem_falhar(canal, rid, msg.telefone, "\n\n".join(respostas))
    return pedido


def _criar_pedido(
    sessao: Session, restaurante: m.Restaurante, cliente_id: uuid.UUID, p: robo.PedidoConfirmado, agora: datetime
) -> m.Pedido:
    return RepoPedidos(sessao, restaurante.id).criar(
        cliente_id=cliente_id,
        data_local=agora_local(restaurante, agora).date(),
        criado_em=agora,
        linhas=[(uuid.UUID(l.item.id), l.item.nome, l.item.preco_centavos, l.quantidade) for l in p.linhas],
        status=StatusPedido.RECEBIDO.value,
        tipo=p.tipo,
        endereco=p.endereco,
        pagamento=p.pagamento,
        troco_para_centavos=p.troco_para_centavos,
        total_centavos=p.total_centavos,
        observacao=p.observacao,
    )
