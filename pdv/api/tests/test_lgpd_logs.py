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


@pytest.mark.bdd("BDD-LGPD-02")
def test_erro_interno_nao_vaza_dados_no_log(sabor, caplog, monkeypatch):
    """Qualquer exceção não tratada vira 500 só com o tipo do erro no log."""
    from pdv_api.repositorios import RepoConversas

    def explode(self, telefone, nome):
        raise RuntimeError(f"falha com {telefone} e {nome}")

    monkeypatch.setattr(RepoConversas, "cliente", explode)
    caplog.set_level(logging.DEBUG)
    from tests.conftest import GATEWAY_TOKEN

    r = sabor.client.post(
        "/canal/webhook",
        json={
            "tipo": "mensagem",
            "restaurante_id": sabor.id,
            "mensagem_id": "x1",
            "telefone": "5592977776666",
            "nome_perfil": "Fulano Secreto",
            "texto": "oi",
        },
        headers={"X-Gateway-Token": GATEWAY_TOKEN},
    )
    assert r.status_code == 500 and r.json() == {"erro": "interno", "detalhe": "erro interno"}
    assert "5592977776666" not in caplog.text and "Fulano Secreto" not in caplog.text
    assert "erro interno RuntimeError em POST /canal/webhook" in caplog.text


def test_mascara_nao_apaga_numeros_curtos():
    """REV-21: datas e números de pedido continuam legíveis; telefones de 10 a 15 dígitos não."""
    assert mascarar_texto("pedido 20261008 nº 123") == "pedido 20261008 nº 123"
    assert mascarar_texto("ddd 9299123456 lid 123456789012345") == "ddd *****-3456 lid *****-2345"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("tel +55 92 99123-4567 ok", "tel *****-4567 ok"),
        ("(92) 99123-4567", "*****-4567"),
        ("fone 99123-4567", "fone *****-4567"),
        ("fixo 3234-1234", "fixo *****-1234"),
        ("hora 12:30 data 2026-10-08", "hora 12:30 data 2026-10-08"),
    ],
)
def test_mascara_telefones_formatados(texto, esperado):
    """REV-23: segunda barreira também para telefone formatado."""
    assert mascarar_texto(texto) == esperado
