"""RF-06, RT-03 · BDD-WA-*"""

from __future__ import annotations

import httpx
import pytest

from pdv_api.dominio.canal import ErroCanal
from pdv_api.gateway_baileys import GatewayBaileys
from tests.conftest import GATEWAY_TOKEN


def _evento_conexao(client, rid, status, qr=None, token=GATEWAY_TOKEN):
    corpo = {"tipo": "status_conexao", "restaurante_id": rid, "status": status}
    if qr:
        corpo["qr_code"] = qr
    return client.post("/canal/webhook", json=corpo, headers={"X-Gateway-Token": token})


@pytest.mark.bdd("BDD-WA-01")
def test_admin_conecta_pelo_qr_code(sabor, canal):
    assert sabor.client.get("/whatsapp/status", headers=sabor.h()).json()["status"] == "desconectado"

    r = sabor.client.post("/whatsapp/conectar", headers=sabor.h())
    assert r.status_code == 202 and r.json() == {"status": "aguardando_qr"}
    assert any(str(s) == sabor.id for s in canal.sessoes)

    qr = "data:image/png;base64,iVBORw0KGgo="
    assert _evento_conexao(sabor.client, sabor.id, "aguardando_qr", qr).status_code == 200
    status = sabor.client.get("/whatsapp/status", headers=sabor.h()).json()
    assert status["status"] == "aguardando_qr" and status["qr_code_data_url"] == qr

    assert _evento_conexao(sabor.client, sabor.id, "conectado").status_code == 200
    status = sabor.client.get("/whatsapp/status", headers=sabor.h()).json()
    assert status["status"] == "conectado" and "qr_code_data_url" not in status


@pytest.mark.bdd("BDD-WA-01")
def test_so_admin_gerencia_conexao(sabor):
    for papel in ("atendente", "cozinha"):
        assert sabor.client.post("/whatsapp/conectar", headers=sabor.h(papel)).status_code == 403
        assert sabor.client.get("/whatsapp/status", headers=sabor.h(papel)).status_code == 403


@pytest.mark.bdd("BDD-WA-02")
def test_sessao_cai_e_admin_gera_novo_qr(sabor, canal):
    sabor.client.post("/whatsapp/conectar", headers=sabor.h())
    _evento_conexao(sabor.client, sabor.id, "conectado")
    _evento_conexao(sabor.client, sabor.id, "desconectado")
    assert sabor.client.get("/whatsapp/status", headers=sabor.h()).json()["status"] == "desconectado"

    canal.sessoes.clear()
    r = sabor.client.post("/whatsapp/conectar", headers=sabor.h())
    assert r.status_code == 202
    assert any(str(s) == sabor.id for s in canal.sessoes)


@pytest.mark.bdd("BDD-WA-02")
def test_admin_desconecta(sabor, canal):
    sabor.client.post("/whatsapp/conectar", headers=sabor.h())
    r = sabor.client.post("/whatsapp/desconectar", headers=sabor.h())
    assert r.status_code == 200
    assert canal.sessoes == set()
    assert sabor.client.get("/whatsapp/status", headers=sabor.h()).json()["status"] == "desconectado"


@pytest.mark.bdd("BDD-WA-03")
@pytest.mark.parametrize("token", [None, "", "token-errado-1234567", GATEWAY_TOKEN + "x"])
def test_webhook_sem_token_valido_retorna_401_e_nao_processa(sabor, canal, token):
    headers = {"X-Gateway-Token": token} if token is not None else {}
    r = sabor.client.post(
        "/canal/webhook",
        json={
            "tipo": "mensagem",
            "restaurante_id": sabor.id,
            "mensagem_id": "wamid-1",
            "telefone": "5592991234567",
            "nome_perfil": "Maria",
            "texto": "oi",
        },
        headers=headers,
    )
    assert r.status_code == 401
    assert canal.enviadas == []


@pytest.mark.bdd("BDD-WA-03")
def test_status_de_conexao_sem_token_retorna_401(sabor):
    r = _evento_conexao(sabor.client, sabor.id, "conectado", token="invalido-invalido")
    assert r.status_code == 401
    assert sabor.client.get("/whatsapp/status", headers=sabor.h()).json()["status"] == "desconectado"


@pytest.mark.bdd("BDD-WA-04")
def test_mensagem_duplicada_nao_gera_resposta_nem_altera_carrinho(sabor, canal):
    tel = "5592991234567"
    sabor.msg(tel, "oi", mensagem_id="wamid-100")
    sabor.msg(tel, "1", mensagem_id="wamid-101")
    sabor.msg(tel, "1", mensagem_id="wamid-102")
    sabor.msg(tel, "2", mensagem_id="wamid-123")  # 2 × Tambaqui
    respostas_antes = len(canal.para(tel))

    resp = sabor.msg(tel, "2", mensagem_id="wamid-123")  # reenvio do gateway
    assert resp == {"ok": True}
    assert len(canal.para(tel)) == respostas_antes

    sabor.msg(tel, "3")  # finaliza: carrinho continua com 2, não 4
    sabor.conversa(tel, "1", "1", "1")
    fila = sabor.fila()
    assert fila[0]["itens"] == [{"nome": "Tambaqui assado", "quantidade": 2}]


def test_webhook_de_restaurante_inexistente_retorna_404(client):
    r = client.post(
        "/canal/webhook",
        json={
            "tipo": "mensagem",
            "restaurante_id": "00000000-0000-0000-0000-000000000000",
            "mensagem_id": "w1",
            "telefone": "5592991234567",
            "texto": "oi",
        },
        headers={"X-Gateway-Token": GATEWAY_TOKEN},
    )
    assert r.status_code == 404


def test_gateway_fora_do_ar_ao_conectar_retorna_503(sabor, canal):
    def falha(_rid):
        raise ErroCanal("fora do ar")

    canal.iniciar_sessao = falha  # type: ignore[method-assign]
    r = sabor.client.post("/whatsapp/conectar", headers=sabor.h())
    assert r.status_code == 503 and r.json()["erro"] == "gateway_indisponivel"


def test_adaptador_gateway_baileys_envia_token_e_corpo():
    chamadas = []

    def tratar(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        return httpx.Response(200, json={"ok": True})

    cliente = httpx.Client(
        base_url="http://gw", headers={"X-Gateway-Token": "t" * 16}, transport=httpx.MockTransport(tratar)
    )
    gw = GatewayBaileys("http://gw", "t" * 16, cliente=cliente)
    import uuid

    rid = uuid.uuid4()
    gw.enviar(rid, "5592991234567", "Olá")
    gw.iniciar_sessao(rid)
    gw.encerrar_sessao(rid)
    assert [(c.method, c.url.path) for c in chamadas] == [
        ("POST", "/mensagens"),
        ("POST", f"/sessoes/{rid}"),
        ("DELETE", f"/sessoes/{rid}"),
    ]
    assert all(c.headers["X-Gateway-Token"] == "t" * 16 for c in chamadas)


def test_adaptador_gateway_baileys_converte_falha_sem_dados_pessoais():
    def tratar(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    cliente = httpx.Client(base_url="http://gw", transport=httpx.MockTransport(tratar))
    gw = GatewayBaileys("http://gw", "t" * 16, cliente=cliente)
    import uuid

    with pytest.raises(ErroCanal) as exc:
        gw.enviar(uuid.uuid4(), "5592991234567", "Rua 10 de Julho")
    assert "5592991234567" not in str(exc.value) and "Rua" not in str(exc.value)

    def cair(req):
        raise httpx.ConnectError("recusada")

    gw2 = GatewayBaileys("http://gw", "t" * 16, cliente=httpx.Client(base_url="http://gw", transport=httpx.MockTransport(cair)))
    with pytest.raises(ErroCanal):
        gw2.iniciar_sessao(uuid.uuid4())
