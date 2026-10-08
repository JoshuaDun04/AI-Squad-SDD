"""Modelo de dados (api-contract-r1 §5). Toda tabela de negócio tem restaurante_id (ADR-0001)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Restaurante(Base):
    __tablename__ = "restaurante"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    nome: Mapped[str] = mapped_column(String(120))
    fuso: Mapped[str] = mapped_column(String(64), default="America/Manaus")


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class TentativaLogin(Base):
    """Falhas de login persistidas (limite sobrevive a reinício e vale entre réplicas)."""

    __tablename__ = "tentativa_login"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave: Mapped[str] = mapped_column(String(300), index=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Categoria(Base):
    __tablename__ = "categoria"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(Base):
    __tablename__ = "item"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), index=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria.id"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str] = mapped_column(String(500), default="")
    preco_centavos: Mapped[int] = mapped_column(Integer)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)


class Horario(Base):
    __tablename__ = "horario"
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), primary_key=True)
    dia_semana: Mapped[int] = mapped_column(Integer, primary_key=True)
    abre: Mapped[time] = mapped_column(Time)
    fecha: Mapped[time] = mapped_column(Time)


class ConexaoWhatsapp(Base):
    __tablename__ = "conexao_whatsapp"
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="desconectado")
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Cliente(Base):
    """RN-10: só telefone e nome do perfil."""

    __tablename__ = "cliente"
    __table_args__ = (UniqueConstraint("restaurante_id", "telefone", name="uq_cliente_telefone"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), index=True)
    telefone: Mapped[str] = mapped_column(String(20))
    nome_perfil: Mapped[str] = mapped_column(String(120), default="")


class Conversa(Base):
    __tablename__ = "conversa"
    __table_args__ = (UniqueConstraint("restaurante_id", "cliente_id", name="uq_conversa_cliente"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), index=True)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cliente.id"))
    estado: Mapped[str] = mapped_column(String(20), default="INICIO")
    carrinho_json: Mapped[list] = mapped_column(JSON, default=list)
    dados_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ultima_msg_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MensagemProcessada(Base):
    __tablename__ = "mensagem_processada"
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"), primary_key=True)
    mensagem_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class Pedido(Base):
    __tablename__ = "pedido"
    __table_args__ = (
        UniqueConstraint("restaurante_id", "data_local", "numero", name="uq_pedido_numero_dia"),
        Index("ix_pedido_fila", "restaurante_id", "status", "criado_em"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    restaurante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurante.id"))
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cliente.id"))
    numero: Mapped[int] = mapped_column(Integer)
    data_local: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(10))
    endereco: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pagamento: Mapped[str] = mapped_column(String(10))
    troco_para_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_centavos: Mapped[int] = mapped_column(Integer)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(300), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PedidoItem(Base):
    """RN-03: nome e preço unitário congelados no momento da confirmação."""

    __tablename__ = "pedido_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("item.id"))
    nome: Mapped[str] = mapped_column(String(120))
    preco_unitario_centavos: Mapped[int] = mapped_column(Integer)
    quantidade: Mapped[int] = mapped_column(Integer)
