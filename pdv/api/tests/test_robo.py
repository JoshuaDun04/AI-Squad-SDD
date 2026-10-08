"""RF-07, RN-04, RN-05, RN-06 · BDD-ROB-* (ponta a ponta pelo webhook)."""

from __future__ import annotations

import pytest

TEL = "5592991234567"


def _ultima(canal, tel=TEL) -> str:
    return canal.para(tel)[-1]


@pytest.mark.bdd("BDD-ROB-01")
def test_cliente_navega_e_adiciona_item(sabor, canal):
    sabor.msg(TEL, "oi")
    assert _ultima(canal) == (
        "Olá! Bem-vindo(a) ao Sabor do Rio.\n\n"
        "Escolha uma categoria:\n1 - Peixes\n2 - Bebidas\n3 - Sobremesas"
    )
    sabor.msg(TEL, "1")
    assert _ultima(canal).startswith("Peixes:\n1 - Tambaqui assado — R$ 45,90\n2 - Pirarucu de casaca — R$ 52,90")
    sabor.msg(TEL, "1")
    assert _ultima(canal) == "Quantas unidades de Tambaqui assado? (1 a 20)"
    sabor.msg(TEL, "2")
    carrinho = _ultima(canal)
    assert "2 × Tambaqui assado — R$ 91,80" in carrinho
    assert "Subtotal: R$ 91,80" in carrinho
    assert carrinho.endswith("1 - Adicionar mais itens, 2 - Remover item, 3 - Finalizar pedido, 0 - Cancelar")


@pytest.mark.bdd("BDD-ROB-02")
def test_remover_item_do_carrinho(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "2", "1", "2", "1", "1")  # 2 Tambaqui + 1 Suco
    sabor.msg(TEL, "2")
    lista = _ultima(canal)
    assert "1 - 2 × Tambaqui assado" in lista and "2 - 1 × Suco de cupuaçu" in lista
    sabor.msg(TEL, "2")
    carrinho = _ultima(canal)
    assert "2 × Tambaqui assado" in carrinho and "Suco" not in carrinho
    assert "Subtotal: R$ 91,80" in carrinho


@pytest.mark.bdd("BDD-ROB-02")
def test_remover_ultimo_item_volta_as_categorias(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "2", "2", "1")
    resposta = _ultima(canal)
    assert "Seu carrinho está vazio." in resposta and "Escolha uma categoria" in resposta


@pytest.mark.bdd("BDD-ROB-03")
def test_mesmo_item_duas_vezes_soma_a_quantidade(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "2")
    sabor.conversa(TEL, "1", "1", "1", "1")  # adicionar mais → Peixes → Tambaqui → 1
    carrinho = _ultima(canal)
    assert "3 × Tambaqui assado — R$ 137,70" in carrinho
    assert carrinho.count("Tambaqui assado") == 1


@pytest.mark.bdd("BDD-ROB-04")
@pytest.mark.parametrize("entrada", ["0", "21", "dois", "2,5", "", "-1", "1e1"])
def test_quantidade_invalida_continua_pedindo(sabor, canal, entrada):
    sabor.conversa(TEL, "oi", "1", "1")
    sabor.msg(TEL, entrada)
    assert _ultima(canal) == "Envie um número de 1 a 20."
    sabor.msg(TEL, "1")  # ainda está pedindo quantidade
    assert "1 × Tambaqui assado" in _ultima(canal)


@pytest.mark.bdd("BDD-ROB-04")
def test_soma_acima_de_20_por_item_e_recusada(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "20", "1", "1", "1")
    sabor.msg(TEL, "1")
    resposta = _ultima(canal)
    assert "limite é 20 unidades de Tambaqui assado" in resposta
    sabor.conversa(TEL, "0")
    assert _ultima(canal) == "Envie um número de 1 a 20."


@pytest.mark.bdd("BDD-ROB-05")
def test_opcao_inexistente_repete_categorias(sabor, canal):
    sabor.msg(TEL, "oi")
    sabor.msg(TEL, "7")
    assert _ultima(canal) == "Opção inválida.\n\nEscolha uma categoria:\n1 - Peixes\n2 - Bebidas\n3 - Sobremesas"


@pytest.mark.bdd("BDD-ROB-05")
@pytest.mark.parametrize("passos,entrada", [(("oi", "1"), "9"), (("oi", "1", "1", "2"), "5"), (("oi", "1", "1", "2", "3"), "x")])
def test_opcao_invalida_em_outros_menus(sabor, canal, passos, entrada):
    sabor.conversa(TEL, *passos)
    sabor.msg(TEL, entrada)
    assert _ultima(canal).startswith("Opção inválida.")


@pytest.mark.bdd("BDD-ROB-06")
def test_carrinho_expira_apos_30_minutos(sabor, canal, relogio):
    sabor.conversa(TEL, "oi", "1", "1", "2")
    relogio.avancar(minutes=31)
    sabor.msg(TEL, "3")
    resposta = _ultima(canal)
    assert "expirou" in resposta and "Escolha uma categoria" in resposta
    assert sabor.fila("admin") == []
    # recomeça do zero: finalizar agora não vê o carrinho antigo
    sabor.msg(TEL, "1")
    assert _ultima(canal).startswith("Peixes:")


@pytest.mark.bdd("BDD-ROB-06")
def test_exatamente_30_minutos_ainda_nao_expira(sabor, canal, relogio):
    sabor.conversa(TEL, "oi", "1", "1", "2")
    relogio.avancar(minutes=30)
    sabor.msg(TEL, "3")
    assert _ultima(canal).startswith("Como você quer receber?")


def test_voltar_das_categorias_ao_carrinho_e_dos_itens(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "0")
    assert _ultima(canal).startswith("Escolha uma categoria")
    sabor.conversa(TEL, "1", "1", "2", "1", "0")
    assert "2 × Tambaqui assado" in _ultima(canal)


def test_cancelar_carrinho(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "2", "0")
    assert _ultima(canal).startswith("Pedido cancelado.")
    sabor.msg(TEL, "oi")
    assert "Bem-vindo" in _ultima(canal)
    assert "0 - Ver carrinho" not in _ultima(canal)


def test_cardapio_vazio(novo_restaurante, canal):
    r = novo_restaurante()
    r.aberto_sempre()
    r.msg(TEL, "oi")
    assert "cardápio está indisponível" in _ultima(canal)


def test_clientes_tem_conversas_separadas(sabor, canal):
    sabor.conversa(TEL, "oi", "1")
    sabor.msg("5592900000000", "oi")
    sabor.msg(TEL, "1")
    assert _ultima(canal) == "Quantas unidades de Tambaqui assado? (1 a 20)"
