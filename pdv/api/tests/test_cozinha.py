"""RF-09, RF-10, RF-11, RN-09, RT-05 · BDD-COZ-*, BDD-CAN-*"""

from __future__ import annotations

import pytest

from tests.conftest import fazer_pedido

TEL1 = "5592911111111"
TEL2 = "5592922222222"


def _status(rest, pedido_id, novo, papel="cozinha"):
    return rest.client.post(f"/pedidos/{pedido_id}/status", json={"novo_status": novo}, headers=rest.h(papel))


def _cancelar(rest, pedido_id, motivo, papel="atendente"):
    return rest.client.post(f"/pedidos/{pedido_id}/cancelar", json={"motivo": motivo}, headers=rest.h(papel))


@pytest.mark.bdd("BDD-COZ-01")
def test_cozinha_prepara_e_cliente_e_avisado(sabor, canal, relogio):
    p1 = fazer_pedido(sabor, TEL1)
    relogio.avancar(minutes=2)
    p2 = fazer_pedido(sabor, TEL2)

    fila = sabor.fila("cozinha")
    assert [p["numero"] for p in fila] == [1, 2]
    assert set(fila[0]) == {"pedido_id", "numero", "status", "criado_em", "tipo", "itens"}  # sem endereço/telefone

    antes = len(canal.para(TEL1))
    assert _status(sabor, p1["pedido_id"], "Em preparo").json() == {"status": "Em preparo"}
    assert _status(sabor, p1["pedido_id"], "Pronto").status_code == 200
    avisos = canal.para(TEL1)[antes:]
    assert avisos == ["Seu pedido #1 está em preparo.", "Seu pedido #1 está pronto! Pode vir retirar."]
    assert [p["status"] for p in sabor.fila()] == ["Pronto", "Recebido"]
    assert canal.para(TEL2)[-1] == "Pedido #2 recebido! Total R$ 100,70"  # #2 não recebeu aviso de #1
    assert p2["numero"] == 2


@pytest.mark.bdd("BDD-COZ-01")
def test_pedido_de_entrega_avisa_saida(sabor, canal):
    p = fazer_pedido(sabor, TEL1, entrega=True)
    _status(sabor, p["pedido_id"], "Em preparo")
    _status(sabor, p["pedido_id"], "Pronto")
    assert canal.para(TEL1)[-1] == "Seu pedido #1 está pronto e vai sair para entrega."


@pytest.mark.bdd("BDD-COZ-01")
def test_pedido_aparece_na_fila_logo_apos_confirmacao(sabor):
    """RT-05: sem fila intermediária; o painel (polling 3 s) vê o pedido na próxima consulta."""
    assert sabor.fila() == []
    fazer_pedido(sabor, TEL1)
    assert len(sabor.fila()) == 1


@pytest.mark.bdd("BDD-COZ-02")
def test_finalizado_sai_da_fila_e_fica_no_historico(sabor, canal):
    p = fazer_pedido(sabor, TEL1)
    for novo in ("Em preparo", "Pronto"):
        _status(sabor, p["pedido_id"], novo)
    r = _status(sabor, p["pedido_id"], "Finalizado", papel="atendente")
    assert r.status_code == 200
    assert sabor.fila() == []
    hist = sabor.client.get("/pedidos", headers=sabor.h("atendente")).json()
    assert hist[0]["status"] == "Finalizado"
    assert canal.para(TEL1)[-1] == "Pedido #1 finalizado. Obrigado pela preferência!"


@pytest.mark.bdd("BDD-COZ-03")
@pytest.mark.parametrize(
    "caminho,novo",
    [
        ([], "Pronto"),  # Recebido → Pronto
        ([], "Finalizado"),
        (["Em preparo", "Pronto"], "Em preparo"),  # Pronto → Em preparo
        (["Em preparo", "Pronto", "Finalizado"], "Recebido"),  # Finalizado → Recebido
        (["Em preparo"], "Em preparo"),
        ([], "Recebido"),
    ],
)
def test_transicao_fora_de_ordem_retorna_409(sabor, canal, caminho, novo):
    p = fazer_pedido(sabor, TEL1)
    for passo in caminho:
        assert _status(sabor, p["pedido_id"], passo).status_code == 200
    atual = caminho[-1] if caminho else "Recebido"
    enviados = len(canal.enviadas)

    r = _status(sabor, p["pedido_id"], novo)
    assert r.status_code == 409 and r.json()["erro"] == "transicao_invalida"
    detalhe = sabor.client.get(f"/pedidos/{p['pedido_id']}", headers=sabor.h()).json()
    assert detalhe["status"] == atual
    assert len(canal.enviadas) == enviados


@pytest.mark.bdd("BDD-COZ-03")
def test_cancelado_e_status_desconhecido(sabor):
    p = fazer_pedido(sabor, TEL1)
    assert _status(sabor, p["pedido_id"], "Cancelado").status_code == 422
    assert _status(sabor, p["pedido_id"], "Saiu").status_code == 422
    assert _status(sabor, "00000000-0000-0000-0000-000000000000", "Em preparo").status_code == 404


@pytest.mark.bdd("BDD-COZ-04")
def test_cozinha_nao_cancela_nem_ve_endereco(sabor):
    p = fazer_pedido(sabor, TEL1, entrega=True)
    assert _cancelar(sabor, p["pedido_id"], "Teste de permissão", papel="cozinha").status_code == 403
    r = sabor.client.get(f"/pedidos/{p['pedido_id']}", headers=sabor.h("cozinha"))
    assert r.status_code == 403
    assert "Rua 10 de Julho" not in r.text
    assert "Rua 10 de Julho" not in sabor.client.get("/fila", headers=sabor.h("cozinha")).text
    assert sabor.fila()[0]["status"] == "Recebido"


@pytest.mark.bdd("BDD-CAN-01")
def test_atendente_cancela_com_motivo(sabor, canal):
    p = fazer_pedido(sabor, TEL1)
    r = _cancelar(sabor, p["pedido_id"], "Cliente desistiu por telefone")
    assert r.status_code == 200 and r.json()["status"] == "Cancelado"
    assert sabor.fila() == []
    assert canal.para(TEL1)[-1] == "Seu pedido #1 foi cancelado. Motivo: Cliente desistiu por telefone"
    detalhe = sabor.client.get(f"/pedidos/{p['pedido_id']}", headers=sabor.h()).json()
    assert detalhe["motivo_cancelamento"] == "Cliente desistiu por telefone"


@pytest.mark.bdd("BDD-CAN-02")
def test_admin_cancela_pedido_em_preparo(sabor, canal):
    p = fazer_pedido(sabor, TEL1)
    _status(sabor, p["pedido_id"], "Em preparo")
    r = _cancelar(sabor, p["pedido_id"], "Falta de ingrediente", papel="admin")
    assert r.status_code == 200
    assert "Motivo: Falta de ingrediente" in canal.para(TEL1)[-1]


@pytest.mark.bdd("BDD-CAN-03")
@pytest.mark.parametrize("motivo", ["", "   ", "ok"])
def test_cancelamento_sem_motivo_retorna_422(sabor, canal, motivo):
    p = fazer_pedido(sabor, TEL1)
    enviados = len(canal.enviadas)
    r = _cancelar(sabor, p["pedido_id"], motivo)
    assert r.status_code == 422
    assert sabor.fila()[0]["status"] == "Recebido"
    assert len(canal.enviadas) == enviados


@pytest.mark.bdd("BDD-CAN-03")
@pytest.mark.parametrize("caminho", [["Em preparo", "Pronto"], ["Em preparo", "Pronto", "Finalizado"]])
def test_cancelamento_apos_pronto_retorna_409(sabor, caminho):
    p = fazer_pedido(sabor, TEL1)
    for passo in caminho:
        _status(sabor, p["pedido_id"], passo)
    r = _cancelar(sabor, p["pedido_id"], "Cliente desistiu")
    assert r.status_code == 409
    detalhe = sabor.client.get(f"/pedidos/{p['pedido_id']}", headers=sabor.h()).json()
    assert detalhe["status"] == caminho[-1]


@pytest.mark.bdd("BDD-CAN-03")
def test_cancelar_duas_vezes_retorna_409(sabor):
    p = fazer_pedido(sabor, TEL1)
    assert _cancelar(sabor, p["pedido_id"], "Primeiro motivo").status_code == 200
    assert _cancelar(sabor, p["pedido_id"], "Segundo motivo").status_code == 409


def test_falha_do_canal_nao_impede_mudanca_de_status(sabor, canal):
    """bdd-r1 'Não aplicável': status muda mesmo se o aviso falhar; falha é registrada."""
    p = fazer_pedido(sabor, TEL1)
    canal.falhar_envio = True
    assert _status(sabor, p["pedido_id"], "Em preparo").status_code == 200
    assert sabor.fila()[0]["status"] == "Em preparo"
