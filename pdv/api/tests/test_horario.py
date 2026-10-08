"""RF-05, RN-07 · BDD-HOR-*"""

from __future__ import annotations

import pytest

from tests.conftest import manaus

TERCA = 1
SEGUNDA = 0


def _abre_terca_a_domingo(rest):
    rest.horarios([{"dia_semana": d, "abre": "11:00", "fecha": "23:00"} for d in range(1, 7)])


@pytest.fixture
def sabor_com_horario(novo_restaurante, relogio):
    relogio.definir(manaus(2026, 10, 6, 22, 0))  # tokens emitidos às 22:00 de terça
    r = novo_restaurante("Sabor do Rio")
    r.criar_usuario("cozinha")
    r.cardapio_padrao()
    _abre_terca_a_domingo(r)
    return r


@pytest.mark.bdd("BDD-HOR-01")
def test_pedido_confirmado_dentro_do_horario(sabor_com_horario, relogio, canal):
    r = sabor_com_horario
    relogio.definir(manaus(2026, 10, 6, 22, 50))  # terça
    r.conversa("5592944445555", "oi", "1", "1", "1", "3", "1", "1")
    relogio.definir(manaus(2026, 10, 6, 22, 59))
    r.msg("5592944445555", "1")  # confirma
    fila = r.fila()
    assert len(fila) == 1
    assert "Pedido #1 recebido!" in canal.para("5592944445555")[-1]


@pytest.mark.bdd("BDD-HOR-01")
def test_horarios_sao_listados_com_estado_atual(sabor_com_horario, relogio):
    r = sabor_com_horario
    relogio.definir(manaus(2026, 10, 6, 12, 0))
    corpo = r.client.get("/horarios", headers=r.h()).json()
    assert corpo["fuso"] == "America/Manaus"
    assert corpo["aberto_agora"] is True
    assert len(corpo["faixas"]) == 6 and corpo["faixas"][0] == {"dia_semana": 1, "abre": "11:00", "fecha": "23:00"}


@pytest.mark.bdd("BDD-HOR-02")
def test_dia_fechado_informa_proxima_abertura_sem_menu(sabor_com_horario, relogio, canal):
    relogio.definir(manaus(2026, 10, 5, 12, 0))  # segunda
    sabor_com_horario.msg("5592944445555", "oi")
    resposta = canal.para("5592944445555")[-1]
    assert "fechado" in resposta
    assert "Abrimos amanhã às 11:00" in resposta
    assert "Escolha uma categoria" not in resposta


@pytest.mark.bdd("BDD-HOR-02")
def test_antes_de_abrir_no_mesmo_dia(sabor_com_horario, relogio, canal):
    relogio.definir(manaus(2026, 10, 6, 9, 30))  # terça cedo
    sabor_com_horario.msg("5592944445555", "oi")
    assert "Abrimos hoje às 11:00" in canal.para("5592944445555")[-1]


@pytest.mark.bdd("BDD-HOR-03")
def test_confirmacao_apos_o_fechamento_nao_cria_pedido(sabor_com_horario, relogio, canal):
    r = sabor_com_horario
    relogio.definir(manaus(2026, 10, 6, 22, 50))
    r.conversa("5592944445555", "oi", "1", "1", "1", "3", "1", "1")
    relogio.definir(manaus(2026, 10, 6, 23, 1))
    r.msg("5592944445555", "1")
    assert r.fila() == []
    resposta = canal.para("5592944445555")[-1]
    assert "fechado" in resposta and "Abrimos amanhã às 11:00" in resposta


@pytest.mark.bdd("BDD-HOR-03")
def test_exatamente_no_horario_de_fechar_ja_esta_fechado(sabor_com_horario, relogio, canal):
    relogio.definir(manaus(2026, 10, 6, 23, 0))
    sabor_com_horario.msg("5592944445555", "oi")
    assert "fechado" in canal.para("5592944445555")[-1]


@pytest.mark.bdd("BDD-HOR-03")
@pytest.mark.parametrize(
    "faixas",
    [
        [{"dia_semana": 1, "abre": "23:00", "fecha": "11:00"}],
        [{"dia_semana": 1, "abre": "11:00", "fecha": "11:00"}],
        [{"dia_semana": 7, "abre": "11:00", "fecha": "23:00"}],
        [{"dia_semana": 1, "abre": "25:00", "fecha": "23:00"}],
        [{"dia_semana": 1, "abre": "11:00", "fecha": "15:00"}, {"dia_semana": 1, "abre": "18:00", "fecha": "23:00"}],
    ],
)
def test_horario_invalido_retorna_422(novo_restaurante, faixas):
    r = novo_restaurante()
    resp = r.client.put("/horarios", json=faixas, headers=r.h())
    assert resp.status_code == 422


def test_fuso_do_restaurante_e_respeitado(novo_restaurante, client, relogio, canal):
    """Restaurante em São Paulo (UTC-3): 22:30 em Manaus já é 23:30 lá."""
    relogio.definir(manaus(2026, 10, 6, 22, 30))
    client.post(
        "/restaurantes",
        json={"nome": "Paulista", "admin_email": "sp@sp.com", "admin_senha": "Forte#2026", "fuso": "America/Sao_Paulo"},
    )
    token = client.post("/auth/login", json={"email": "sp@sp.com", "senha": "Forte#2026"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    client.put("/horarios", json=[{"dia_semana": TERCA, "abre": "11:00", "fecha": "23:00"}], headers=h)
    assert client.get("/horarios", headers=h).json()["aberto_agora"] is False


def test_fuso_invalido_recusado(client):
    r = client.post(
        "/restaurantes",
        json={"nome": "X", "admin_email": "x@x.com", "admin_senha": "Forte#2026", "fuso": "Marte/Base"},
    )
    assert r.status_code == 422
