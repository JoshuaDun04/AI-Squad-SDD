"""RF-08, RN-02, RN-03, RN-07, RN-08, RT-08 · BDD-PED-*"""

from __future__ import annotations

import pytest

from tests.conftest import manaus

TEL = "5592991234567"


def _ultima(canal, tel=TEL) -> str:
    return canal.para(tel)[-1]


@pytest.mark.bdd("BDD-PED-01")
def test_retirada_com_pix_cria_pedido(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "2", "1", "2", "1", "1", "3")
    sabor.msg(TEL, "1")  # retirada
    assert _ultima(canal).startswith("Forma de pagamento:")
    sabor.msg(TEL, "1")  # pix
    resumo = _ultima(canal)
    assert "Total: R$ 100,70" in resumo and "Retirada no local" in resumo and "Pagamento: Pix" in resumo
    sabor.msg(TEL, "1")  # confirma
    assert _ultima(canal) == "Pedido #1 recebido! Total R$ 100,70"

    fila = sabor.fila()
    assert len(fila) == 1
    assert fila[0]["numero"] == 1 and fila[0]["status"] == "Recebido" and fila[0]["tipo"] == "retirada"

    detalhe = sabor.client.get(f"/pedidos/{fila[0]['pedido_id']}", headers=sabor.h("atendente")).json()
    assert detalhe["total_centavos"] == 10070
    assert detalhe["pagamento"] == "pix" and detalhe["troco_para_centavos"] is None
    precos = {i["nome"]: (i["preco_unitario_centavos"], i["quantidade"]) for i in detalhe["itens"]}
    assert precos == {"Tambaqui assado": (4590, 2), "Suco de cupuaçu": (890, 1)}


@pytest.mark.bdd("BDD-PED-02")
def test_entrega_com_dinheiro_e_troco(novo_restaurante, canal):
    r = novo_restaurante()
    r.aberto_sempre()
    r.categoria("Lanches")
    r.item("Lanches", "X-Caboquinho", 1290)  # 3 × 12,90 = 38,70
    r.conversa(TEL, "oi", "1", "1", "3", "3", "2")
    r.msg(TEL, "Rua 10 de Julho, 500, Centro")
    r.msg(TEL, "2")  # dinheiro
    assert 'Total R$ 38,70. Troco para quanto?' in _ultima(canal)
    r.msg(TEL, "50")
    resumo = _ultima(canal)
    assert "Entrega em: Rua 10 de Julho, 500, Centro" in resumo
    assert "Dinheiro (troco para R$ 50,00)" in resumo
    r.msg(TEL, "1")

    pedido = r.client.get("/pedidos", headers=r.h()).json()[0]
    detalhe = r.client.get(f"/pedidos/{pedido['pedido_id']}", headers=r.h()).json()
    assert detalhe["tipo"] == "entrega"
    assert detalhe["endereco"] == "Rua 10 de Julho, 500, Centro"
    assert detalhe["troco_para_centavos"] == 5000
    assert detalhe["total_centavos"] == 3870


@pytest.mark.bdd("BDD-PED-02")
@pytest.mark.parametrize("texto,esperado", [("sem troco", None), ("Sem  Troco", None), ("38,70", 3870), ("R$ 100", 10000)])
def test_formatos_de_troco_aceitos(novo_restaurante, canal, texto, esperado):
    r = novo_restaurante()
    r.aberto_sempre()
    r.categoria("Lanches")
    r.item("Lanches", "X-Caboquinho", 1290)
    r.conversa(TEL, "oi", "1", "1", "3", "3", "1", "2", texto, "1")
    pedido = r.client.get("/pedidos", headers=r.h()).json()[0]
    detalhe = r.client.get(f"/pedidos/{pedido['pedido_id']}", headers=r.h()).json()
    assert detalhe["troco_para_centavos"] == esperado


@pytest.mark.bdd("BDD-PED-03")
def test_numeracao_diaria_reinicia_a_meia_noite_local(novo_restaurante, canal, relogio):
    from tests.conftest import fazer_pedido

    relogio.definir(manaus(2026, 10, 6, 23, 0))
    r = novo_restaurante()
    r.aberto_sempre()
    r.cardapio_padrao()
    r.criar_usuario("cozinha")
    numeros = [fazer_pedido(r, telefone=f"55929000000{i:02d}")["numero"] for i in range(3)]
    assert numeros == [1, 2, 3]

    # 00:05 em Manaus = 04:05 UTC; em UTC o dia já tinha virado às 20:00 de Manaus
    relogio.definir(manaus(2026, 10, 7, 0, 5))
    novo = fazer_pedido(r, telefone="5592911110000")
    assert novo["numero"] == 1
    datas = {p["numero"]: p for p in r.client.get("/pedidos?data=2026-10-06", headers=r.h()).json()}
    assert sorted(datas) == [1, 2, 3]


@pytest.mark.bdd("BDD-PED-03")
def test_preco_congelado_apos_mudanca(sabor, canal):
    from tests.conftest import fazer_pedido

    pedido = fazer_pedido(sabor)
    r = sabor.client.patch(f"/itens/{sabor.itens['Tambaqui assado']}", json={"preco_centavos": 4990}, headers=sabor.h())
    assert r.status_code == 200
    detalhe = sabor.client.get(f"/pedidos/{pedido['pedido_id']}", headers=sabor.h()).json()
    precos = {i["nome"]: i["preco_unitario_centavos"] for i in detalhe["itens"]}
    assert precos["Tambaqui assado"] == 4590
    assert detalhe["total_centavos"] == 10070


@pytest.mark.bdd("BDD-PED-03")
def test_preco_vale_o_do_momento_da_confirmacao(sabor, canal):
    """Preço muda com o carrinho aberto: o pedido usa o preço vigente ao confirmar (RN-03)."""
    sabor.conversa(TEL, "oi", "1", "1", "2", "3", "1", "1")
    sabor.client.patch(f"/itens/{sabor.itens['Tambaqui assado']}", json={"preco_centavos": 5000}, headers=sabor.h())
    sabor.msg(TEL, "1")
    assert _ultima(canal) == "Pedido #1 recebido! Total R$ 100,00"


@pytest.mark.bdd("BDD-PED-04")
@pytest.mark.parametrize("troco", ["30", "38,69", "abc", "0", "-50"])
def test_troco_menor_que_total_e_recusado(novo_restaurante, canal, troco):
    r = novo_restaurante()
    r.aberto_sempre()
    r.categoria("Lanches")
    r.item("Lanches", "X-Caboquinho", 1290)
    r.conversa(TEL, "oi", "1", "1", "3", "3", "1", "2")
    r.msg(TEL, troco)
    assert _ultima(canal) == 'O troco precisa ser para um valor maior ou igual a R$ 38,70, ou envie "sem troco".'
    assert r.client.get("/pedidos", headers=r.h()).json() == []
    r.msg(TEL, "1")  # ainda pedindo troco; "1" = R$ 1,00 também é recusado
    assert r.client.get("/pedidos", headers=r.h()).json() == []


@pytest.mark.bdd("BDD-PED-05")
@pytest.mark.parametrize("endereco", ["", "   ", "Rua 10", "Centro 5"])
def test_entrega_sem_endereco_completo(sabor, canal, endereco):
    sabor.conversa(TEL, "oi", "1", "1", "1", "3", "2")
    sabor.msg(TEL, endereco)
    assert _ultima(canal).startswith("Envie o endereço completo")
    sabor.msg(TEL, "Rua 10 de Julho, 500, Centro")
    assert _ultima(canal).startswith("Forma de pagamento:")


@pytest.mark.bdd("BDD-PED-06")
def test_finalizar_quando_carrinho_esvaziou(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "1")
    sabor.client.patch(f"/itens/{sabor.itens['Tambaqui assado']}", json={"disponivel": False}, headers=sabor.h())
    sabor.msg(TEL, "3")
    resposta = _ultima(canal)
    assert "Seu carrinho está vazio." in resposta and "Escolha uma categoria" in resposta
    assert sabor.fila() == []


def test_confirmacao_pode_voltar_ao_carrinho_ou_cancelar(sabor, canal):
    sabor.conversa(TEL, "oi", "1", "1", "1", "3", "1", "1", "2")
    assert "1 × Tambaqui assado" in _ultima(canal)
    sabor.conversa(TEL, "3", "1", "1", "0")
    assert _ultima(canal).startswith("Pedido cancelado.")
    assert sabor.fila() == []


def test_historico_do_dia_para_atendente(sabor, canal):
    from tests.conftest import fazer_pedido

    fazer_pedido(sabor)
    hist = sabor.client.get("/pedidos", headers=sabor.h("atendente")).json()
    assert len(hist) == 1 and hist[0]["total_centavos"] == 10070
    assert sabor.client.get("/pedidos?data=2026-10-05", headers=sabor.h("atendente")).json() == []
    assert sabor.client.get("/pedidos", headers=sabor.h("cozinha")).status_code == 403
