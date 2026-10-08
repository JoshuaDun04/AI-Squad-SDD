"""RN-01 no nível dos repositórios (REV-08): cada método, chamado com o restaurante A,
não enxerga nem altera nada do restaurante B. Um teste por filtro de `restaurante_id`."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, UTC

import pytest

from pdv_api import modelos as m
from pdv_api.repositorios import (
    RepoCardapio,
    RepoConexao,
    RepoConversas,
    RepoHorarios,
    RepoPedidos,
    RepoUsuarios,
)
from tests.conftest import fazer_pedido

TEL_B = "5592988887777"


@pytest.fixture
def dois(sabor, tacaca, fabrica):
    """A = Sabor do Rio, B = Tacacá da Praça, cada um com um pedido de entrega."""
    fazer_pedido(sabor, "5592911112222", entrega=True)
    tacaca.conversa(TEL_B, "oi", "1", "1", "1", "3", "2", "Travessa da Praça, 10", "1", "1")
    with fabrica() as s:
        b = uuid.UUID(tacaca.id)
        pedido_b = s.query(m.Pedido).filter_by(restaurante_id=b).one()
        dados = {
            "a": uuid.UUID(sabor.id),
            "b": b,
            "pedido_b": pedido_b.id,
            "cliente_b": pedido_b.cliente_id,
            "data_b": pedido_b.data_local,
            "usuario_b": s.query(m.Usuario).filter_by(restaurante_id=b).first().id,
            "categoria_b": uuid.UUID(tacaca.categorias["Tacacás"]),
            "item_b": uuid.UUID(tacaca.itens["Tacacá grande"]),
        }
    return dados


@pytest.mark.bdd("BDD-ISO-01")
def test_repo_pedidos(dois, fabrica):
    with fabrica() as s:
        repo = RepoPedidos(s, dois["a"])
        assert repo.obter(dois["pedido_b"]) is None
        assert repo.obter(dois["pedido_b"], para_atualizar=True) is None
        assert repo.itens(dois["pedido_b"]) == []
        assert repo.itens_de([dois["pedido_b"]]) == {}
        assert all(p.restaurante_id == dois["a"] for p in repo.fila())
        assert len(repo.fila()) == 1
        assert all(p.restaurante_id == dois["a"] for p in repo.do_dia(dois["data_b"]))
        assert len(repo.do_dia(dois["data_b"])) == 1


@pytest.mark.bdd("BDD-ISO-01")
def test_repo_conversas(dois, fabrica):
    with fabrica() as s:
        repo = RepoConversas(s, dois["a"])
        assert repo.obter_cliente(dois["cliente_b"]) is None
        # mesmo telefone em A é outro cliente, com outra conversa
        cliente_a = repo.cliente(TEL_B, "Maria")
        assert cliente_a.id != dois["cliente_b"] and cliente_a.restaurante_id == dois["a"]
        conversa_a = repo.conversa_travada(cliente_a.id)
        assert conversa_a.restaurante_id == dois["a"] and conversa_a.estado == "INICIO"
        # o mesmo mensagem_id pode existir nos dois restaurantes
        assert RepoConversas(s, dois["b"]).reservar_mensagem("igual") is True
        assert repo.reservar_mensagem("igual") is True
        s.rollback()


@pytest.mark.bdd("BDD-ISO-01")
def test_limpeza_de_conversas_so_no_proprio_restaurante(dois, fabrica, tacaca):
    tacaca.conversa("5592933330000", "oi", "1")  # conversa de B no meio do menu
    with fabrica() as s:
        apagadas = RepoConversas(s, dois["a"]).limpar_abandonadas(datetime.now(UTC) + timedelta(days=1))
        s.commit()
        conversas_b = s.query(m.Conversa).filter_by(restaurante_id=dois["b"]).all()
        assert any(c.estado != "INICIO" for c in conversas_b)
        assert apagadas >= 0


@pytest.mark.bdd("BDD-ISO-02")
def test_repo_cardapio(dois, fabrica):
    with fabrica() as s:
        repo = RepoCardapio(s, dois["a"])
        assert repo.obter_categoria(dois["categoria_b"]) is None
        assert repo.obter_item(dois["item_b"]) is None
        assert repo.categoria_tem_itens(dois["categoria_b"]) is False
        assert repo.listar_itens(dois["categoria_b"]) == []
        assert dois["item_b"] not in {i.id for i in repo.listar_itens()}
        assert dois["categoria_b"] not in {c.id for c in repo.listar_categorias()}
        assert dois["item_b"] not in {i.id for _, itens in repo.cardapio_disponivel() for i in itens}
        cat_b = s.get(m.Categoria, dois["categoria_b"])
        with pytest.raises(PermissionError):
            repo.remover_categoria(cat_b)


@pytest.mark.bdd("BDD-ISO-02")
def test_repo_usuarios(dois, fabrica, sabor):
    with fabrica() as s:
        repo = RepoUsuarios(s, dois["a"])
        assert repo.obter(dois["usuario_b"]) is None
        assert dois["usuario_b"] not in {u.id for u in repo.listar()}
    r = sabor.client.patch(f"/usuarios/{dois['usuario_b']}", json={"ativo": False}, headers=sabor.h())
    assert r.status_code == 404
    with fabrica() as s:
        assert s.get(m.Usuario, dois["usuario_b"]).ativo is True


@pytest.mark.bdd("BDD-ISO-02")
def test_repo_horarios_e_conexao(dois, fabrica):
    agora = datetime.now(UTC)
    with fabrica() as s:
        RepoConexao(s, dois["b"]).definir("conectado", None, agora)
        s.commit()
        assert RepoConexao(s, dois["a"]).obter() is None
        RepoConexao(s, dois["a"]).definir("aguardando_qr", "data:x", agora)
        RepoHorarios(s, dois["a"]).substituir([(0, time(8), time(9))])
        s.commit()
        assert RepoConexao(s, dois["b"]).obter().status == "conectado"
        assert len(RepoHorarios(s, dois["b"]).listar()) == 7  # B continua com os 7 dias
        assert [h.dia_semana for h in RepoHorarios(s, dois["a"]).listar()] == [0]


@pytest.mark.bdd("BDD-ISO-03")
def test_numeracao_independente_por_restaurante(dois, fabrica):
    with fabrica() as s:
        hoje = dois["data_b"]
        assert RepoPedidos(s, dois["a"])._proximo_numero(hoje) == 2
        assert RepoPedidos(s, dois["b"])._proximo_numero(hoje) == 2
        s.rollback()
