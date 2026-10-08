"""RN-01, RT-01 · BDD-ISO-* — nada de um restaurante aparece ou muda no outro."""

from __future__ import annotations

import pytest

from tests.conftest import fazer_pedido


@pytest.mark.bdd("BDD-ISO-01")
def test_pedido_de_outro_restaurante_retorna_404_sem_vazar_campos(sabor, tacaca):
    pedido_b = None
    tacaca.conversa("5592988887777", "oi", "1", "1", "1", "3", "1", "1", "1")
    pedido_b = tacaca.fila()[0]

    r = sabor.client.get(f"/pedidos/{pedido_b['pedido_id']}", headers=sabor.h("atendente"))
    assert r.status_code == 404
    corpo = r.text
    assert "Tacacá" not in corpo and "5592988887777" not in corpo and str(pedido_b["numero"]) not in r.json().get("detalhe", "")
    assert set(r.json()) == {"erro", "detalhe"}


@pytest.mark.bdd("BDD-ISO-01")
@pytest.mark.parametrize("acao", ["status", "cancelar"])
def test_alterar_pedido_de_outro_restaurante_retorna_404(sabor, tacaca, acao):
    tacaca.conversa("5592988887777", "oi", "1", "1", "1", "3", "1", "1", "1")
    pedido_b = tacaca.fila()[0]
    if acao == "status":
        r = sabor.client.post(f"/pedidos/{pedido_b['pedido_id']}/status", json={"novo_status": "Em preparo"}, headers=sabor.h())
    else:
        r = sabor.client.post(f"/pedidos/{pedido_b['pedido_id']}/cancelar", json={"motivo": "teste"}, headers=sabor.h())
    assert r.status_code == 404
    assert tacaca.fila()[0]["status"] == "Recebido"


@pytest.mark.bdd("BDD-ISO-02")
def test_alterar_item_de_outro_restaurante_retorna_404_e_preco_nao_muda(sabor, tacaca):
    item_b = tacaca.itens["Tacacá grande"]
    r = sabor.client.patch(f"/itens/{item_b}", json={"preco_centavos": 100}, headers=sabor.h())
    assert r.status_code == 404
    itens_b = tacaca.client.get("/itens", headers=tacaca.h()).json()
    assert itens_b[0]["preco_centavos"] == 2500


@pytest.mark.bdd("BDD-ISO-02")
def test_categoria_de_outro_restaurante_inacessivel(sabor, tacaca):
    cat_b = tacaca.categorias["Tacacás"]
    assert sabor.client.patch(f"/categorias/{cat_b}", json={"nome": "X"}, headers=sabor.h()).status_code == 404
    assert sabor.client.delete(f"/categorias/{cat_b}", headers=sabor.h()).status_code == 404
    # nem como referência ao criar item
    r = sabor.client.post(
        "/itens", json={"categoria_id": cat_b, "nome": "Invasor", "preco_centavos": 100}, headers=sabor.h()
    )
    assert r.status_code == 422
    assert [c["nome"] for c in tacaca.client.get("/categorias", headers=tacaca.h()).json()] == ["Tacacás"]


@pytest.mark.bdd("BDD-ISO-02")
def test_listagens_so_trazem_o_proprio_restaurante(sabor, tacaca):
    nomes_a = {i["nome"] for i in sabor.client.get("/itens", headers=sabor.h()).json()}
    assert "Tacacá grande" not in nomes_a
    ids_a = {u["id"] for u in sabor.client.get("/usuarios", headers=sabor.h()).json()}
    ids_b = {u["id"] for u in tacaca.client.get("/usuarios", headers=tacaca.h()).json()}
    assert ids_a and ids_b and not ids_a & ids_b


@pytest.mark.bdd("BDD-ISO-03")
def test_fila_da_cozinha_nao_mistura_restaurantes(sabor, tacaca):
    fazer_pedido(sabor)
    tacaca.conversa("5592988887777", "oi", "1", "1", "1", "3", "1", "1", "1")
    fila_a = sabor.fila("cozinha")
    fila_b = tacaca.fila("cozinha")
    assert len(fila_a) == 1 and len(fila_b) == 1
    assert {i["nome"] for i in fila_a[0]["itens"]} == {"Tambaqui assado", "Suco de cupuaçu"}
    assert fila_b[0]["itens"][0]["nome"] == "Tacacá grande"
    # numeração é por restaurante: os dois começam em 1
    assert fila_a[0]["numero"] == 1 and fila_b[0]["numero"] == 1


@pytest.mark.bdd("BDD-ISO-03")
def test_mensagem_de_whatsapp_so_ve_cardapio_do_proprio_restaurante(sabor, tacaca, canal):
    tacaca.msg("5592900001111", "oi")
    resposta = canal.para("5592900001111")[-1]
    assert "Tacacás" in resposta and "Peixes" not in resposta


def test_repositorio_exige_restaurante_id(fabrica):
    from pdv_api.repositorios import RepoPedidos

    with fabrica() as s, pytest.raises(ValueError):
        RepoPedidos(s, None)  # type: ignore[arg-type]
