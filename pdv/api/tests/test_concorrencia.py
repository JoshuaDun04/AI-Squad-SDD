"""Concorrência real (REV-01, REV-02, REV-04). Roda em PostgreSQL e em SQLite em arquivo
(o banco do app Windows, ADR-0012). O SQLite em memória usa uma conexão única e não
reproduz travas entre transações."""

from __future__ import annotations

import logging
import os
import threading
import uuid

import pytest

from pdv_api.dominio.canal import CanalEmMemoria
from pdv_api.servicos.robo_servico import MensagemRecebida, processar_mensagem

_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not (_URL.startswith("postgresql") or (_URL.startswith("sqlite") and ":memory:" not in _URL and _URL.count("/") >= 3)),
    reason="concorrência real exige PostgreSQL ou SQLite em arquivo (TEST_DATABASE_URL)",
)


def _em_paralelo(funcoes):
    barreira = threading.Barrier(len(funcoes))
    erros: list[BaseException] = []

    def rodar(f):
        try:
            barreira.wait()
            f()
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=rodar, args=(f,)) for f in funcoes]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return erros


def _mensagem(fabrica, relogio, canal, rid, telefone, texto, nome="Maria"):
    def f():
        with fabrica() as s:
            processar_mensagem(
                s, MensagemRecebida(uuid.UUID(rid), f"w-{uuid.uuid4()}", telefone, nome, texto), relogio, canal
            )

    return f


def test_confirmacoes_simultaneas_criam_um_pedido_so(sabor, fabrica, relogio):
    tel = "5592990001111"
    sabor.conversa(tel, "oi", "1", "1", "2", "3", "1", "1")  # no resumo
    canal = CanalEmMemoria()
    erros = _em_paralelo([_mensagem(fabrica, relogio, canal, sabor.id, tel, "1") for _ in range(4)])
    assert erros == []
    assert len(sabor.fila()) == 1
    assert sum("recebido!" in t for t in canal.para(tel)) == 1


def test_primeira_mensagem_simultanea_de_cliente_novo(sabor, fabrica, relogio, caplog):
    caplog.set_level(logging.DEBUG)
    tel = "5592908887776"
    canal = CanalEmMemoria()
    erros = _em_paralelo(
        [_mensagem(fabrica, relogio, canal, sabor.id, tel, "oi", nome="Maria Sonda") for _ in range(6)]
    )
    assert erros == []
    assert len(canal.para(tel)) == 6
    assert tel not in caplog.text and "Maria Sonda" not in caplog.text


def test_numeracao_simultanea_sem_buracos_nem_erro(sabor, fabrica, relogio):
    tels = [f"55929100000{i:02d}" for i in range(8)]
    for tel in tels:
        sabor.conversa(tel, "oi", "1", "1", "1", "3", "1", "1")
    canal = CanalEmMemoria()
    erros = _em_paralelo([_mensagem(fabrica, relogio, canal, sabor.id, tel, "1") for tel in tels])
    assert erros == []
    assert sorted(p["numero"] for p in sabor.fila()) == list(range(1, 9))


def test_duplicata_simultanea_da_mesma_mensagem(sabor, fabrica, relogio):
    tel = "5592990002222"
    sabor.conversa(tel, "oi", "1", "1", "2", "3", "1", "1")
    canal = CanalEmMemoria()

    def mesma():
        with fabrica() as s:
            processar_mensagem(s, MensagemRecebida(uuid.UUID(sabor.id), "wamid-igual", tel, "Maria", "1"), relogio, canal)

    assert _em_paralelo([mesma for _ in range(4)]) == []
    assert len(sabor.fila()) == 1
    assert len(canal.para(tel)) == 1
