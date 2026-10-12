"""RF-21, RF-23, RN-24 · BDD-INS-* (app Windows: um restaurante por instalação)."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from pdv_api.config import Config
from pdv_api.main import criar_app
from tests.conftest import GATEWAY_TOKEN, JWT_SECRET

SABOR = {"nome": "Sabor do Rio", "admin_email": "dono@sabor.com", "admin_senha": "Forte#2026"}
TACACA = {"nome": "Tacacá da Praça", "admin_email": "dono@tacaca.com", "admin_senha": "Forte#2026"}


def _cliente(canal, relogio, fabrica, **opcoes) -> TestClient:
    cfg = Config(database_url="sqlite://", jwt_secret=JWT_SECRET, gateway_token=GATEWAY_TOKEN, **opcoes)
    return TestClient(criar_app(cfg, canal_mensagens=canal, relogio=relogio, fabrica_sessao=fabrica))


@pytest.fixture
def local(canal, relogio, fabrica) -> TestClient:
    return _cliente(canal, relogio, fabrica, restaurante_unico=True, endereco_rede="http://192.168.0.10:8080")


@pytest.mark.bdd("BDD-INS-01")
def test_primeiro_uso_cadastra_e_fecha_o_cadastro(local):
    antes = local.get("/instalacao").json()
    assert antes["modo"] == "local" and antes["cadastro_aberto"] is True

    assert local.post("/restaurantes", json=SABOR).status_code == 201
    assert local.get("/instalacao").json()["cadastro_aberto"] is False
    # o dono continua entrando normalmente
    assert local.post("/auth/login", json={"email": SABOR["admin_email"], "senha": SABOR["admin_senha"]}).status_code == 200


@pytest.mark.bdd("BDD-INS-02")
def test_instalacao_informa_endereco_para_a_cozinha(local):
    assert local.get("/instalacao").json()["endereco_rede"] == "http://192.168.0.10:8080"


@pytest.mark.bdd("BDD-INS-02")
def test_sem_endereco_configurado_vem_nulo(canal, relogio, fabrica):
    cliente = _cliente(canal, relogio, fabrica, restaurante_unico=True)
    assert cliente.get("/instalacao").json()["endereco_rede"] is None


@pytest.mark.bdd("BDD-INS-03")
def test_segundo_restaurante_e_recusado(local):
    assert local.post("/restaurantes", json=SABOR).status_code == 201
    r = local.post("/restaurantes", json=TACACA)
    assert r.status_code == 409 and r.json()["erro"] == "restaurante_ja_cadastrado"
    login = local.post("/auth/login", json={"email": TACACA["admin_email"], "senha": TACACA["admin_senha"]})
    assert login.status_code == 401  # nada foi criado


@pytest.mark.bdd("BDD-INS-03")
def test_cadastros_simultaneos_criam_um_so(local, engine):
    """BEGIN IMMEDIATE (ADR-0012) serializa a verificação e o cadastro."""
    if engine.dialect.name == "sqlite" and engine.url.database in (None, "", ":memory:"):
        pytest.skip("concorrência real exige banco em arquivo ou PostgreSQL")
    codigos: list[int] = []
    barreira = threading.Barrier(4)

    def cadastrar(i: int) -> None:
        barreira.wait()
        dados = {**SABOR, "admin_email": f"dono{i}@sabor.com"}
        codigos.append(local.post("/restaurantes", json=dados).status_code)

    threads = [threading.Thread(target=cadastrar, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sorted(codigos) == [201, 409, 409, 409]


def test_modo_servidor_continua_aceitando_varios(client):
    """Sem PDV_RESTAURANTE_UNICO o comportamento da R1 não muda."""
    assert client.get("/instalacao").json() == {"modo": "servidor", "cadastro_aberto": True, "endereco_rede": None}
    assert client.post("/restaurantes", json=SABOR).status_code == 201
    assert client.post("/restaurantes", json=TACACA).status_code == 201


def test_configuracao_pelo_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("GATEWAY_TOKEN", GATEWAY_TOKEN)
    monkeypatch.setenv("PDV_RESTAURANTE_UNICO", "1")
    monkeypatch.setenv("PDV_ENDERECO_REDE", " http://10.0.0.5:8080 ")
    cfg = Config.do_ambiente()
    assert cfg.restaurante_unico is True and cfg.endereco_rede == "http://10.0.0.5:8080"
