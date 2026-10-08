"""SEC-02, SEC-03: segredos fortes obrigatórios e CORS desligado por padrão."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pdv_api.config import Config, ConfigInvalida
from pdv_api.main import criar_app
from tests.conftest import GATEWAY_TOKEN, JWT_SECRET


@pytest.mark.parametrize(
    "ambiente",
    [
        {"DATABASE_URL": "sqlite://", "JWT_SECRET": "curto", "GATEWAY_TOKEN": GATEWAY_TOKEN},
        {"DATABASE_URL": "sqlite://", "JWT_SECRET": JWT_SECRET, "GATEWAY_TOKEN": "curto"},
        {"DATABASE_URL": "", "JWT_SECRET": JWT_SECRET, "GATEWAY_TOKEN": GATEWAY_TOKEN},
        {},
    ],
)
def test_api_recusa_iniciar_com_segredo_fraco(monkeypatch, ambiente):
    for chave in ("DATABASE_URL", "JWT_SECRET", "GATEWAY_TOKEN"):
        monkeypatch.delenv(chave, raising=False)
    for chave, valor in ambiente.items():
        monkeypatch.setenv(chave, valor)
    with pytest.raises(ConfigInvalida):
        Config.do_ambiente()


def test_config_do_ambiente_valida(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("GATEWAY_TOKEN", GATEWAY_TOKEN)
    monkeypatch.setenv("CORS_ORIGENS", "https://painel.exemplo.com, ")
    c = Config.do_ambiente()
    assert c.cors_origens == ("https://painel.exemplo.com",)


def test_cors_desligado_por_padrao(config, canal, relogio, fabrica):
    app = criar_app(config, canal_mensagens=canal, relogio=relogio, fabrica_sessao=fabrica)
    r = TestClient(app).get("/saude", headers={"Origin": "https://malicioso.com"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_cors_liberado_so_para_origem_configurada(canal, relogio, fabrica):
    cfg = Config(database_url="sqlite://", jwt_secret=JWT_SECRET, gateway_token=GATEWAY_TOKEN, cors_origens=("https://painel.com",))
    cliente = TestClient(criar_app(cfg, canal_mensagens=canal, relogio=relogio, fabrica_sessao=fabrica))
    assert cliente.get("/saude", headers={"Origin": "https://painel.com"}).headers["access-control-allow-origin"] == "https://painel.com"
    assert "access-control-allow-origin" not in cliente.get("/saude", headers={"Origin": "https://outro.com"}).headers
