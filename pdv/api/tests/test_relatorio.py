"""RF-27 · BDD-REL-* relatório do piloto no painel."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from pdv_api.servicos.relatorio import PedidoRel, montar, percentil
from tests.conftest import fazer_pedido, manaus

TEL1, TEL2, TEL3 = "5592911111111", "5592922222222", "5592933333333"


def _status(rest, pid, novo, papel="cozinha"):
    r = rest.client.post(f"/pedidos/{pid}/status", json={"novo_status": novo}, headers=rest.h(papel))
    assert r.status_code == 200, r.text


@pytest.mark.bdd("BDD-REL-01")
def test_admin_ve_os_numeros_do_piloto(sabor, relogio):
    p1 = fazer_pedido(sabor, TEL1)  # 2 Tambaqui + 1 Suco = 100,70
    relogio.avancar(minutes=3)
    _status(sabor, p1["pedido_id"], "Em preparo")
    relogio.avancar(minutes=12)
    _status(sabor, p1["pedido_id"], "Pronto")
    relogio.avancar(minutes=10)
    _status(sabor, p1["pedido_id"], "Finalizado", papel="atendente")
    p2 = fazer_pedido(sabor, TEL2, entrega=True)
    relogio.avancar(minutes=5)
    _status(sabor, p2["pedido_id"], "Em preparo")

    r = sabor.client.get("/relatorio?dias=7", headers=sabor.h())
    assert r.status_code == 200
    rel = r.json()
    assert rel["dias"] == 7 and rel["ate"] == "2026-10-06"
    assert rel["por_dia"] == [
        {
            "dia": "2026-10-06",
            "pedidos": 2,
            "finalizados": 1,
            "cancelados": 0,
            "em_aberto": 1,
            "entregas": 1,
            "ticket_medio_centavos": 10070,
            "vendido_centavos": 20140,
        }
    ]
    assert rel["tempos"]["ate_preparo"] == {"pedidos": 2, "mediana_min": 4.0, "p90_min": 4.8}
    assert rel["tempos"]["preparo"] == {"pedidos": 1, "mediana_min": 12.0, "p90_min": 12.0}
    assert rel["tempos"]["pronto_ate_finalizado"]["mediana_min"] == 10.0
    assert rel["por_hora"] == [{"hora": 12, "pedidos": 2}]
    assert rel["itens_mais_pedidos"][0] == {"nome": "Tambaqui assado", "unidades": 4}
    assert rel["whatsapp"] == "desconectado"


@pytest.mark.bdd("BDD-REL-02")
def test_periodo_e_cancelados(sabor, relogio):
    relogio.definir(manaus(2026, 9, 26, 12))  # 10 dias antes
    fazer_pedido(sabor, TEL1)
    relogio.definir(manaus(2026, 10, 6, 12))
    sabor.criar_usuario("atendente")
    sabor.criar_usuario("cozinha")
    fazer_pedido(sabor, TEL2)
    cancelado = fazer_pedido(sabor, TEL3)
    r = sabor.client.post(
        f"/pedidos/{cancelado['pedido_id']}/cancelar", json={"motivo": "Cliente desistiu"}, headers=sabor.h("atendente")
    )
    assert r.status_code == 200

    sete = sabor.client.get("/relatorio?dias=7", headers=sabor.h()).json()
    assert [d["dia"] for d in sete["por_dia"]] == ["2026-10-06"]
    assert sete["totais"] == {"pedidos": 2, "cancelados": 1, "vendido_centavos": 10070, "ticket_medio_centavos": 10070}
    assert sete["cancelamentos"] == [{"motivo": "Cliente desistiu", "vezes": 1}]
    assert sete["itens_mais_pedidos"][0]["unidades"] == 2  # cancelado não conta

    trinta = sabor.client.get("/relatorio?dias=30", headers=sabor.h()).json()
    assert [d["dia"] for d in trinta["por_dia"]] == ["2026-09-26", "2026-10-06"]


@pytest.mark.bdd("BDD-REL-03")
@pytest.mark.parametrize("papel", ["cozinha", "atendente"])
def test_so_admin_ve_relatorio(sabor, papel):
    assert sabor.client.get("/relatorio", headers=sabor.h(papel)).status_code == 403


@pytest.mark.bdd("BDD-REL-03")
@pytest.mark.parametrize("dias", ["0", "-1", "367", "abc"])
def test_periodo_invalido(sabor, dias):
    assert sabor.client.get(f"/relatorio?dias={dias}", headers=sabor.h()).status_code == 422


@pytest.mark.bdd("BDD-REL-03")
def test_relatorio_sem_dados_pessoais(sabor):
    fazer_pedido(sabor, TEL1, entrega=True)
    texto = sabor.client.get("/relatorio", headers=sabor.h()).text
    assert TEL1 not in texto and "Rua 10 de Julho" not in texto and "Maria" not in texto


def test_relatorio_isolado_por_restaurante(sabor, tacaca):
    fazer_pedido(sabor, TEL1)
    rel_b = tacaca.client.get("/relatorio", headers=tacaca.h()).json()
    assert rel_b["totais"]["pedidos"] == 0 and rel_b["por_dia"] == []


def test_relatorio_vazio():
    rel = montar([], [], "America/Manaus", 7)
    assert rel["totais"] == {"pedidos": 0, "cancelados": 0, "vendido_centavos": 0, "ticket_medio_centavos": None}
    assert rel["tempos"]["preparo"] == {"pedidos": 0, "mediana_min": None, "p90_min": None}


@pytest.mark.parametrize(
    "valores,p,esperado",
    [([], 0.5, None), ([5], 0.9, 5), ([3, 5], 0.5, 4.0), ([3, 5], 0.9, 4.8), ([1, 2, 3, 4], 0.5, 2.5), ([10, 1, 4], 0.5, 4)],
)
def test_percentil_igual_ao_postgres(valores, p, esperado):
    assert percentil(valores, p) == esperado


def test_hora_no_fuso_do_restaurante():
    criado = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)  # 23:30 do dia 5 em Manaus
    ped = PedidoRel(date(2026, 10, 5), "Recebido", "retirada", 1000, None, criado, None, None, None)
    assert montar([ped], [], "America/Manaus", 7)["por_hora"] == [{"hora": 23, "pedidos": 1}]
    assert montar([ped], [], "America/Sao_Paulo", 7)["por_hora"] == [{"hora": 0, "pedidos": 1}]
    sem_fuso = PedidoRel(date(2026, 10, 5), "Recebido", "retirada", 1000, None, criado.replace(tzinfo=None),
                         criado.replace(tzinfo=None) + timedelta(minutes=2), None, None)
    assert montar([sem_fuso], [], "America/Manaus", 7)["tempos"]["ate_preparo"]["mediana_min"] == 2.0
