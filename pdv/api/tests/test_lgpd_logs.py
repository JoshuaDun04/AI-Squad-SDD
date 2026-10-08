"""RN-10, RT-06 · BDD-LGPD-*"""

from __future__ import annotations

import logging

import pytest

from pdv_api.dominio.lgpd import FiltroDadosPessoais, mascarar_telefone, mascarar_texto
from tests.conftest import fazer_pedido

TEL = "5592991234567"


@pytest.mark.bdd("BDD-LGPD-01")
def test_pedido_de_retirada_guarda_so_o_necessario(sabor, fabrica):
    p = fazer_pedido(sabor, TEL)
    detalhe = sabor.client.get(f"/pedidos/{p['pedido_id']}", headers=sabor.h()).json()
    assert detalhe["endereco"] is None
    assert detalhe["cliente"] == {"nome_perfil": "Maria", "telefone": TEL}

    from pdv_api import modelos as m

    colunas_cliente = {c.name for c in m.Cliente.__table__.columns}
    assert colunas_cliente == {"id", "restaurante_id", "telefone", "nome_perfil"}


@pytest.mark.bdd("BDD-LGPD-02")
def test_logs_nao_contem_telefone_nem_endereco(sabor, canal, caplog):
    caplog.set_level(logging.DEBUG)
    canal.falhar_envio = True  # o erro do canal carrega telefone e texto na mensagem
    sabor.conversa(TEL, "oi", "1", "1", "1", "3", "2", "Rua 10 de Julho, 500, Centro", "1", "1")
    canal.falhar_envio = False

    todos = "\n".join(r.getMessage() for r in caplog.records)
    assert "falha ao enviar mensagem" in todos
    assert TEL not in todos
    assert "Rua 10 de Julho" not in todos
    assert "*****-4567" in todos


@pytest.mark.bdd("BDD-LGPD-02")
def test_filtro_mascara_telefone_que_escapar_para_o_log(caplog):
    logger = logging.getLogger("teste.lgpd")
    logger.addFilter(FiltroDadosPessoais())
    with caplog.at_level(logging.INFO, logger="teste.lgpd"):
        logger.info("cliente %s mandou mensagem", TEL)
    assert TEL not in caplog.text and "*****-4567" in caplog.text


@pytest.mark.bdd("BDD-LGPD-02")
@pytest.mark.parametrize(
    "entrada,saida",
    [
        ("5592991234567", "*****-4567"),
        ("+55 92 99123-4567", "*****-4567"),
        ("123", "*****"),
        ("", "*****"),
    ],
)
def test_mascarar_telefone(entrada, saida):
    assert mascarar_telefone(entrada) == saida


def test_mascarar_texto_preserva_datas_e_ids():
    texto = "pedido 2026-10-06 numero 12 uuid 99ba63af-fdc7 tel 5592991234567"
    assert mascarar_texto(texto) == "pedido 2026-10-06 numero 12 uuid 99ba63af-fdc7 tel *****-4567"
