"""RF-04, RN-02, RN-04 · BDD-CAR-*"""

from __future__ import annotations

import pytest


@pytest.mark.bdd("BDD-CAR-01")
def test_admin_monta_o_cardapio(novo_restaurante):
    r = novo_restaurante()
    cat = r.categoria("Peixes")
    item = r.item("Peixes", "Tambaqui assado", 4590)
    itens = r.client.get(f"/itens?categoria_id={cat}", headers=r.h()).json()
    assert itens == [
        {
            "id": item,
            "categoria_id": cat,
            "nome": "Tambaqui assado",
            "descricao": "",
            "preco_centavos": 4590,
            "disponivel": True,
            "ordem": 0,
        }
    ]


@pytest.mark.bdd("BDD-CAR-01")
def test_ordenacao_e_edicao_de_categorias(novo_restaurante):
    r = novo_restaurante()
    r.categoria("Bebidas", 2)
    r.categoria("Peixes", 1)
    assert [c["nome"] for c in r.client.get("/categorias", headers=r.h()).json()] == ["Peixes", "Bebidas"]
    resp = r.client.patch(f"/categorias/{r.categorias['Bebidas']}", json={"ordem": 0}, headers=r.h())
    assert resp.status_code == 200
    assert [c["nome"] for c in r.client.get("/categorias", headers=r.h()).json()] == ["Bebidas", "Peixes"]


@pytest.mark.bdd("BDD-CAR-02")
def test_item_desativado_some_do_robo_mas_fica_no_painel(sabor, canal):
    item = sabor.itens["Tambaqui assado"]
    r = sabor.client.patch(f"/itens/{item}", json={"disponivel": False}, headers=sabor.h())
    assert r.status_code == 200 and r.json()["disponivel"] is False

    painel = {i["nome"]: i for i in sabor.client.get("/itens", headers=sabor.h()).json()}
    assert painel["Tambaqui assado"]["disponivel"] is False

    sabor.conversa("5592911112222", "oi", "1")  # Peixes
    menu_peixes = canal.para("5592911112222")[-1]
    assert "Tambaqui assado" not in menu_peixes
    assert "Pirarucu de casaca" in menu_peixes


@pytest.mark.bdd("BDD-CAR-02")
def test_categoria_sem_itens_disponiveis_nao_aparece_no_robo(sabor, canal):
    sabor.client.patch(f"/itens/{sabor.itens['Pudim']}", json={"disponivel": False}, headers=sabor.h())
    sabor.msg("5592911112222", "oi")
    assert "Sobremesas" not in canal.para("5592911112222")[-1]


@pytest.mark.bdd("BDD-CAR-03")
@pytest.mark.parametrize("preco", [0, -100, 12.90, "12.90", "1290", None, True])
def test_preco_invalido_retorna_422_e_nao_salva(novo_restaurante, preco):
    r = novo_restaurante()
    r.categoria("Peixes")
    resp = r.client.post(
        "/itens",
        json={"categoria_id": r.categorias["Peixes"], "nome": "Tambaqui", "preco_centavos": preco},
        headers=r.h(),
    )
    assert resp.status_code == 422
    assert resp.json()["erro"] == "validacao"
    assert r.client.get("/itens", headers=r.h()).json() == []


@pytest.mark.bdd("BDD-CAR-03")
@pytest.mark.parametrize("preco", [0, -100, 12.90])
def test_preco_invalido_na_edicao_retorna_422(sabor, preco):
    item = sabor.itens["Tambaqui assado"]
    resp = sabor.client.patch(f"/itens/{item}", json={"preco_centavos": preco}, headers=sabor.h())
    assert resp.status_code == 422
    precos = {i["nome"]: i["preco_centavos"] for i in sabor.client.get("/itens", headers=sabor.h()).json()}
    assert precos["Tambaqui assado"] == 4590


@pytest.mark.bdd("BDD-CAR-04")
def test_item_que_ficou_indisponivel_sai_do_carrinho_com_aviso(sabor, canal):
    tel = "5592933334444"
    sabor.conversa(tel, "oi", "1", "1", "2")  # 2 × Tambaqui no carrinho
    sabor.client.patch(f"/itens/{sabor.itens['Tambaqui assado']}", json={"disponivel": False}, headers=sabor.h())

    sabor.msg(tel, "3")  # tenta finalizar
    resposta = canal.para(tel)[-1]
    assert "Tambaqui assado ficou indisponível e foi removido do carrinho" in resposta
    assert "carrinho está vazio" in resposta
    assert sabor.fila() == []


@pytest.mark.bdd("BDD-CAR-04")
def test_item_indisponivel_no_meio_do_fechamento_volta_ao_carrinho(sabor, canal):
    tel = "5592933334444"
    sabor.conversa(tel, "oi", "1", "1", "2", "1", "2", "1", "1", "3", "1", "1")  # está na confirmação
    sabor.client.patch(f"/itens/{sabor.itens['Tambaqui assado']}", json={"disponivel": False}, headers=sabor.h())
    sabor.msg(tel, "1")  # confirmar
    resposta = canal.para(tel)[-1]
    assert "Tambaqui assado ficou indisponível e foi removido do carrinho" in resposta
    assert "1 × Suco de cupuaçu" in resposta and "Finalizar pedido" in resposta
    assert sabor.fila() == []


def test_categoria_com_itens_nao_pode_ser_apagada(sabor):
    r = sabor.client.delete(f"/categorias/{sabor.categorias['Peixes']}", headers=sabor.h())
    assert r.status_code == 409
    vazia = sabor.categoria("Vazia")
    assert sabor.client.delete(f"/categorias/{vazia}", headers=sabor.h()).status_code == 204


def test_campos_desconhecidos_sao_recusados(sabor):
    r = sabor.client.patch(f"/itens/{sabor.itens['Pudim']}", json={"restaurante_id": "x"}, headers=sabor.h())
    assert r.status_code == 422


def test_item_inexistente_retorna_404(sabor):
    r = sabor.client.patch("/itens/00000000-0000-0000-0000-000000000000", json={"nome": "X"}, headers=sabor.h())
    assert r.status_code == 404
