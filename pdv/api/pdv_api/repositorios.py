"""Repositórios: única porta de acesso ao banco (ADR-0001).

Todo repositório de dados de negócio recebe `restaurante_id` no construtor e
filtra todas as consultas por ele. Recurso de outro restaurante simplesmente
"não existe" (None), e as rotas respondem 404 (RN-01).

Exceções explícitas, sem filtro por restaurante:
- RepoRestaurantes: cria/consulta o próprio restaurante.
- RepoAutenticacao: login por e-mail (global) e carga do usuário do token.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dominio.status import STATUS_NA_FILA


class RepoRestaurantes:
    def __init__(self, sessao: Session) -> None:
        self.s = sessao

    def criar(self, nome: str, fuso: str) -> m.Restaurante:
        r = m.Restaurante(nome=nome, fuso=fuso)
        self.s.add(r)
        self.s.flush()
        return r

    def obter(self, restaurante_id: uuid.UUID) -> m.Restaurante | None:
        return self.s.get(m.Restaurante, restaurante_id)


class RepoAutenticacao:
    def __init__(self, sessao: Session) -> None:
        self.s = sessao

    def usuario_por_email(self, email: str) -> m.Usuario | None:
        return self.s.scalar(select(m.Usuario).where(m.Usuario.email == email.lower()))

    def usuario_por_id(self, usuario_id: uuid.UUID) -> m.Usuario | None:
        return self.s.get(m.Usuario, usuario_id)

    def email_em_uso(self, email: str) -> bool:
        return self.usuario_por_email(email) is not None

    def falhas_recentes(self, chave: str, desde: datetime) -> int:
        return self.s.scalar(
            select(func.count()).select_from(m.TentativaLogin).where(
                m.TentativaLogin.chave == chave, m.TentativaLogin.momento >= desde
            )
        ) or 0

    def registrar_falha(self, chave: str, momento: datetime) -> None:
        self.s.add(m.TentativaLogin(chave=chave, momento=momento))

    def limpar_falhas(self, chave: str, antes_de: datetime | None = None) -> None:
        stmt = delete(m.TentativaLogin).where(m.TentativaLogin.chave == chave)
        self.s.execute(stmt)
        if antes_de is not None:
            self.s.execute(delete(m.TentativaLogin).where(m.TentativaLogin.momento < antes_de))


class _RepoDoRestaurante:
    def __init__(self, sessao: Session, restaurante_id: uuid.UUID) -> None:
        if restaurante_id is None:
            raise ValueError("restaurante_id é obrigatório")
        self.s = sessao
        self.rid = restaurante_id


class RepoUsuarios(_RepoDoRestaurante):
    def listar(self) -> list[m.Usuario]:
        return list(
            self.s.scalars(select(m.Usuario).where(m.Usuario.restaurante_id == self.rid).order_by(m.Usuario.email))
        )

    def obter(self, usuario_id: uuid.UUID) -> m.Usuario | None:
        return self.s.scalar(
            select(m.Usuario).where(m.Usuario.id == usuario_id, m.Usuario.restaurante_id == self.rid)
        )

    def criar(self, email: str, senha_hash: str, papel: str) -> m.Usuario:
        u = m.Usuario(restaurante_id=self.rid, email=email.lower(), senha_hash=senha_hash, papel=papel, ativo=True)
        self.s.add(u)
        self.s.flush()
        return u


class RepoCardapio(_RepoDoRestaurante):
    def listar_categorias(self) -> list[m.Categoria]:
        return list(
            self.s.scalars(
                select(m.Categoria)
                .where(m.Categoria.restaurante_id == self.rid)
                .order_by(m.Categoria.ordem, m.Categoria.nome)
            )
        )

    def obter_categoria(self, categoria_id: uuid.UUID) -> m.Categoria | None:
        return self.s.scalar(
            select(m.Categoria).where(m.Categoria.id == categoria_id, m.Categoria.restaurante_id == self.rid)
        )

    def criar_categoria(self, nome: str, ordem: int, ativa: bool) -> m.Categoria:
        c = m.Categoria(restaurante_id=self.rid, nome=nome, ordem=ordem, ativa=ativa)
        self.s.add(c)
        self.s.flush()
        return c

    def categoria_tem_itens(self, categoria_id: uuid.UUID) -> bool:
        return bool(
            self.s.scalar(
                select(func.count())
                .select_from(m.Item)
                .where(m.Item.categoria_id == categoria_id, m.Item.restaurante_id == self.rid)
            )
        )

    def remover_categoria(self, categoria: m.Categoria) -> None:
        if categoria.restaurante_id != self.rid:  # defesa extra
            raise PermissionError("categoria de outro restaurante")
        self.s.delete(categoria)

    def listar_itens(self, categoria_id: uuid.UUID | None = None) -> list[m.Item]:
        stmt = select(m.Item).where(m.Item.restaurante_id == self.rid)
        if categoria_id is not None:
            stmt = stmt.where(m.Item.categoria_id == categoria_id)
        return list(self.s.scalars(stmt.order_by(m.Item.ordem, m.Item.nome)))

    def obter_item(self, item_id: uuid.UUID) -> m.Item | None:
        return self.s.scalar(select(m.Item).where(m.Item.id == item_id, m.Item.restaurante_id == self.rid))

    def criar_item(self, **campos: object) -> m.Item:
        it = m.Item(restaurante_id=self.rid, **campos)
        self.s.add(it)
        self.s.flush()
        return it

    def cardapio_disponivel(self) -> list[tuple[m.Categoria, list[m.Item]]]:
        """Categorias ativas com itens disponíveis, na ordem do cardápio (robô)."""
        cats = [c for c in self.listar_categorias() if c.ativa]
        itens = self.s.scalars(
            select(m.Item)
            .where(m.Item.restaurante_id == self.rid, m.Item.disponivel.is_(True))
            .order_by(m.Item.ordem, m.Item.nome)
        )
        por_cat: dict[uuid.UUID, list[m.Item]] = {}
        for it in itens:
            por_cat.setdefault(it.categoria_id, []).append(it)
        return [(c, por_cat[c.id]) for c in cats if por_cat.get(c.id)]


class RepoHorarios(_RepoDoRestaurante):
    def listar(self) -> list[m.Horario]:
        return list(
            self.s.scalars(
                select(m.Horario).where(m.Horario.restaurante_id == self.rid).order_by(m.Horario.dia_semana)
            )
        )

    def substituir(self, faixas: list[tuple[int, object, object]]) -> list[m.Horario]:
        self.s.execute(delete(m.Horario).where(m.Horario.restaurante_id == self.rid))
        novos = [m.Horario(restaurante_id=self.rid, dia_semana=d, abre=a, fecha=f) for d, a, f in faixas]
        self.s.add_all(novos)
        self.s.flush()
        return novos


class RepoConexao(_RepoDoRestaurante):
    def obter(self) -> m.ConexaoWhatsapp | None:
        return self.s.scalar(select(m.ConexaoWhatsapp).where(m.ConexaoWhatsapp.restaurante_id == self.rid))

    def definir(self, status: str, qr_code: str | None, agora: datetime) -> m.ConexaoWhatsapp:
        c = self.obter()
        if c is None:
            c = m.ConexaoWhatsapp(restaurante_id=self.rid)
            self.s.add(c)
        c.status = status
        c.qr_code = qr_code if status == "aguardando_qr" else None
        c.atualizado_em = agora
        self.s.flush()
        return c


class RepoConversas(_RepoDoRestaurante):
    def mensagem_ja_processada(self, mensagem_id: str) -> bool:
        return (
            self.s.scalar(
                select(func.count())
                .select_from(m.MensagemProcessada)
                .where(m.MensagemProcessada.restaurante_id == self.rid, m.MensagemProcessada.mensagem_id == mensagem_id)
            )
            or 0
        ) > 0

    def marcar_processada(self, mensagem_id: str) -> None:
        self.s.add(m.MensagemProcessada(restaurante_id=self.rid, mensagem_id=mensagem_id))

    def cliente(self, telefone: str, nome_perfil: str) -> m.Cliente:
        c = self.s.scalar(
            select(m.Cliente).where(m.Cliente.restaurante_id == self.rid, m.Cliente.telefone == telefone)
        )
        if c is None:
            c = m.Cliente(restaurante_id=self.rid, telefone=telefone, nome_perfil=nome_perfil or "")
            self.s.add(c)
            self.s.flush()
        elif nome_perfil and c.nome_perfil != nome_perfil:
            c.nome_perfil = nome_perfil
        return c

    def obter_cliente(self, cliente_id: uuid.UUID) -> m.Cliente | None:
        return self.s.scalar(
            select(m.Cliente).where(m.Cliente.id == cliente_id, m.Cliente.restaurante_id == self.rid)
        )

    def conversa(self, cliente_id: uuid.UUID) -> m.Conversa:
        c = self.s.scalar(
            select(m.Conversa).where(m.Conversa.restaurante_id == self.rid, m.Conversa.cliente_id == cliente_id)
        )
        if c is None:
            c = m.Conversa(restaurante_id=self.rid, cliente_id=cliente_id, estado="INICIO", carrinho_json=[], dados_json={})
            self.s.add(c)
            self.s.flush()
        return c


class RepoPedidos(_RepoDoRestaurante):
    def obter(self, pedido_id: uuid.UUID, para_atualizar: bool = False) -> m.Pedido | None:
        stmt = select(m.Pedido).where(m.Pedido.id == pedido_id, m.Pedido.restaurante_id == self.rid)
        if para_atualizar:  # trava a linha: dois atendentes não aplicam a mesma transição
            stmt = stmt.with_for_update()
        return self.s.scalar(stmt)

    def itens(self, pedido_id: uuid.UUID) -> list[m.PedidoItem]:
        # pedido_id já validado pelo chamador via obter()/fila(); junta para garantir o restaurante
        return list(
            self.s.scalars(
                select(m.PedidoItem)
                .join(m.Pedido, m.Pedido.id == m.PedidoItem.pedido_id)
                .where(m.PedidoItem.pedido_id == pedido_id, m.Pedido.restaurante_id == self.rid)
                .order_by(m.PedidoItem.id)
            )
        )

    def itens_de(self, pedido_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[m.PedidoItem]]:
        if not pedido_ids:
            return {}
        linhas = self.s.scalars(
            select(m.PedidoItem)
            .join(m.Pedido, m.Pedido.id == m.PedidoItem.pedido_id)
            .where(m.PedidoItem.pedido_id.in_(pedido_ids), m.Pedido.restaurante_id == self.rid)
            .order_by(m.PedidoItem.id)
        )
        res: dict[uuid.UUID, list[m.PedidoItem]] = {}
        for li in linhas:
            res.setdefault(li.pedido_id, []).append(li)
        return res

    def fila(self) -> list[m.Pedido]:
        return list(
            self.s.scalars(
                select(m.Pedido)
                .where(m.Pedido.restaurante_id == self.rid, m.Pedido.status.in_([s.value for s in STATUS_NA_FILA]))
                .order_by(m.Pedido.criado_em, m.Pedido.numero)
            )
        )

    def do_dia(self, data_local: date) -> list[m.Pedido]:
        return list(
            self.s.scalars(
                select(m.Pedido)
                .where(m.Pedido.restaurante_id == self.rid, m.Pedido.data_local == data_local)
                .order_by(m.Pedido.numero)
            )
        )

    def _proximo_numero(self, data_local: date) -> int:
        atual = self.s.scalar(
            select(func.max(m.Pedido.numero)).where(
                m.Pedido.restaurante_id == self.rid, m.Pedido.data_local == data_local
            )
        )
        return (atual or 0) + 1

    def criar(
        self,
        *,
        cliente_id: uuid.UUID,
        data_local: date,
        criado_em: datetime,
        linhas: list[tuple[uuid.UUID, str, int, int]],  # item_id, nome, preço, quantidade
        **campos: object,
    ) -> m.Pedido:
        """RT-08: número sequencial por restaurante e dia local; tenta de novo em corrida."""
        for _ in range(5):
            savepoint = self.s.begin_nested()
            try:
                pedido = m.Pedido(
                    restaurante_id=self.rid,
                    cliente_id=cliente_id,
                    numero=self._proximo_numero(data_local),
                    data_local=data_local,
                    criado_em=criado_em,
                    **campos,
                )
                self.s.add(pedido)
                self.s.flush()
                for item_id, nome, preco, qtd in linhas:
                    self.s.add(
                        m.PedidoItem(
                            pedido_id=pedido.id,
                            item_id=item_id,
                            nome=nome,
                            preco_unitario_centavos=preco,
                            quantidade=qtd,
                        )
                    )
                self.s.flush()
                savepoint.commit()
                return pedido
            except IntegrityError:
                savepoint.rollback()
        raise RuntimeError("não foi possível numerar o pedido")


def limite_janela(agora: datetime, minutos: int) -> datetime:
    return agora - timedelta(minutes=minutos)
