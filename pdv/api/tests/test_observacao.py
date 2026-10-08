"""RF-08, RN-11, DEC-07 · BDD-OBS-* — observação livre do pedido."""

from __future__ import annotations

import logging

import pytest

TEL = "5592991234567"
ATE_O_RESUMO = ("oi", "1", "1", "2", "3", "1", "1")  # 2 × Tambaqui, retirada, Pix


def _ultima(canal) -> str:
    return canal.para(TEL)[-1]


@pytest.mark.bdd("BDD-OBS-01")
def test_observacao_vai_para_o_pedido_e_para_a_fila(sabor, canal):
    sabor.conversa(TEL, *ATE_O_RESUMO, "3")
    assert _ultima(canal).startswith("Escreva a observação para a cozinha")
    sabor.msg(TEL, "  tambaqui   sem cebola ")
    resumo = _ultima(canal)
    assert "Observação: tambaqui sem cebola" in resumo
    assert "3 - Alterar observação" in resumo
    sabor.msg(TEL, "1")

    fila = sabor.fila("cozinha")
    assert fila[0]["observacao"] == "tambaqui sem cebola"
    detalhe = sabor.client.get(f"/pedidos/{fila[0]['pedido_id']}", headers=sabor.h()).json()
    assert detalhe["observacao"] == "tambaqui sem cebola"


@pytest.mark.bdd("BDD-OBS-02")
def test_cliente_remove_a_observacao(sabor, canal):
    sabor.conversa(TEL, *ATE_O_RESUMO, "3", "sem cebola", "3", "0")
    resumo = _ultima(canal)
    assert "Observação:" not in resumo and "3 - Adicionar observação" in resumo
    sabor.msg(TEL, "1")
    assert sabor.fila()[0]["observacao"] is None


@pytest.mark.bdd("BDD-OBS-02")
def test_pedido_sem_observacao_por_padrao(sabor):
    sabor.conversa(TEL, *ATE_O_RESUMO, "1")
    assert sabor.fila()[0]["observacao"] is None


@pytest.mark.bdd("BDD-OBS-03")
@pytest.mark.parametrize("texto", ["x" * 141, "palavra " * 30])
def test_observacao_longa_e_recusada(sabor, canal, texto):
    sabor.conversa(TEL, *ATE_O_RESUMO, "3")
    sabor.msg(TEL, texto)
    assert _ultima(canal).startswith("A observação pode ter no máximo 140 caracteres.")
    assert sabor.fila() == []
    sabor.msg(TEL, "x" * 140)  # exatamente no limite é aceito
    assert f"Observação: {'x' * 140}" in _ultima(canal)


@pytest.mark.bdd("BDD-OBS-03")
def test_observacao_vazia_pede_de_novo(sabor, canal):
    sabor.conversa(TEL, *ATE_O_RESUMO, "3")
    sabor.msg(TEL, "   ")
    assert _ultima(canal).startswith("Escreva a observação para a cozinha")


def test_observacao_nao_vai_para_o_log(sabor, canal, caplog):
    caplog.set_level(logging.DEBUG)
    canal.falhar_envio = True
    sabor.conversa(TEL, *ATE_O_RESUMO, "3", "alergia a camarão", "1")
    assert "camarão" not in caplog.text
