"""RF-01, RF-02, RF-03, RT-02 · BDD-AUT-*"""

from __future__ import annotations

import pytest

from pdv_api.seguranca import ler_token
from tests.conftest import JWT_SECRET


@pytest.mark.bdd("BDD-AUT-01")
def test_cadastro_e_login_do_admin(client, fabrica, relogio):
    r = client.post(
        "/restaurantes", json={"nome": "Sabor do Rio", "admin_email": "dono@sabor.com", "admin_senha": "Forte#2026"}
    )
    assert r.status_code == 201
    rid = r.json()["restaurante_id"]

    login = client.post("/auth/login", json={"email": "dono@sabor.com", "senha": "Forte#2026"})
    assert login.status_code == 200
    corpo = login.json()
    assert corpo["papel"] == "admin" and corpo["restaurante_id"] == rid

    principal = ler_token(corpo["token"], relogio.agora(), JWT_SECRET)
    assert str(principal.restaurante_id) == rid and principal.papel == "admin"

    eu = client.get("/auth/eu", headers={"Authorization": f"Bearer {corpo['token']}"}).json()
    assert eu["restaurante_nome"] == "Sabor do Rio"

    # senha nunca em texto puro
    from pdv_api.repositorios import RepoAutenticacao

    with fabrica() as s:
        usuario = RepoAutenticacao(s).usuario_por_email("dono@sabor.com")
        assert usuario.senha_hash != "Forte#2026"
        assert usuario.senha_hash.startswith("$argon2")


@pytest.mark.bdd("BDD-AUT-01")
def test_email_ja_usado_retorna_409(client):
    dados = {"nome": "Sabor do Rio", "admin_email": "dono@sabor.com", "admin_senha": "Forte#2026"}
    assert client.post("/restaurantes", json=dados).status_code == 201
    r = client.post("/restaurantes", json={**dados, "nome": "Outro"})
    assert r.status_code == 409
    assert r.json()["erro"] == "email_em_uso"


@pytest.mark.bdd("BDD-AUT-02")
def test_admin_cria_usuario_cozinha_com_acesso_restrito(sabor):
    # sabor já criou o usuário "cozinha" via POST /usuarios e fez login
    assert sabor.client.get("/fila", headers=sabor.h("cozinha")).status_code == 200
    r = sabor.client.patch(
        f"/itens/{sabor.itens['Tambaqui assado']}", json={"preco_centavos": 1}, headers=sabor.h("cozinha")
    )
    assert r.status_code == 403
    r = sabor.client.post("/categorias", json={"nome": "X"}, headers=sabor.h("cozinha"))
    assert r.status_code == 403
    assert sabor.client.get("/usuarios", headers=sabor.h("cozinha")).status_code == 403


@pytest.mark.bdd("BDD-AUT-03")
def test_senha_incorreta_retorna_401(sabor):
    sabor.criar_usuario("atendente", email="atendente@sabor.com")
    r = sabor.client.post("/auth/login", json={"email": "atendente@sabor.com", "senha": "errada!!"})
    assert r.status_code == 401
    assert "token" not in r.json()


@pytest.mark.bdd("BDD-AUT-03")
def test_usuario_desativado_perde_acesso_na_hora(sabor):
    uid = sabor.criar_usuario("atendente", email="atendente@sabor.com")
    token_antigo = sabor.h("atendente")
    assert sabor.client.get("/fila", headers=token_antigo).status_code == 200

    r = sabor.client.patch(f"/usuarios/{uid}", json={"ativo": False}, headers=sabor.h())
    assert r.status_code == 200 and r.json()["ativo"] is False

    r = sabor.client.get("/fila", headers=token_antigo)
    assert r.status_code == 401
    assert r.json()["erro"] == "nao_autenticado"
    login = sabor.client.post("/auth/login", json={"email": "atendente@sabor.com", "senha": "Senha#Forte1"})
    assert login.status_code == 401


@pytest.mark.bdd("BDD-AUT-03")
def test_token_com_mais_de_8_horas_retorna_401(sabor, relogio):
    sabor.criar_usuario("atendente", email="atendente@sabor.com")
    h = sabor.h("atendente")
    relogio.avancar(hours=7, minutes=59)
    assert sabor.client.get("/fila", headers=h).status_code == 200
    relogio.avancar(minutes=2)
    r = sabor.client.get("/fila", headers=h)
    assert r.status_code == 401
    assert r.json()["detalhe"] == "token expirado"


@pytest.mark.bdd("BDD-AUT-03")
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer", "Bearer abc.def.ghi", "Basic dXNlcjpwYXNz"],
)
def test_token_ausente_ou_malformado_retorna_401(sabor, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    assert sabor.client.get("/fila", headers=headers).status_code == 401


@pytest.mark.bdd("BDD-AUT-03")
def test_token_assinado_com_outro_segredo_retorna_401(sabor, relogio):
    from pdv_api.seguranca import Principal, emitir_token
    import uuid

    falso = emitir_token(
        Principal(uuid.uuid4(), uuid.UUID(sabor.id), "admin"), relogio.agora(), "x" * 40
    )
    assert sabor.client.get("/fila", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_limite_de_tentativas_de_login(client, relogio):
    """SEC-01: 5 falhas em 15 min bloqueiam com 429; persiste no banco."""
    client.post("/restaurantes", json={"nome": "Sabor do Rio", "admin_email": "dono@sabor.com", "admin_senha": "Forte#2026"})
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "dono@sabor.com", "senha": "errada!!"}).status_code == 401
    r = client.post("/auth/login", json={"email": "dono@sabor.com", "senha": "Forte#2026"})
    assert r.status_code == 429
    relogio.avancar(minutes=16)
    assert client.post("/auth/login", json={"email": "dono@sabor.com", "senha": "Forte#2026"}).status_code == 200


def test_admin_nao_desativa_a_si_mesmo(sabor):
    eu = sabor.client.get("/auth/eu", headers=sabor.h()).json()
    r = sabor.client.patch(f"/usuarios/{eu['usuario_id']}", json={"ativo": False}, headers=sabor.h())
    assert r.status_code == 422


def test_usuarios_validacao_e_listagem(sabor):
    r = sabor.client.post("/usuarios", json={"email": "x@x.com", "senha": "curta", "papel": "cozinha"}, headers=sabor.h())
    assert r.status_code == 422
    r = sabor.client.post("/usuarios", json={"email": "x@x.com", "senha": "Senha#Forte1", "papel": "gerente"}, headers=sabor.h())
    assert r.status_code == 422
    papeis = sorted(u["papel"] for u in sabor.client.get("/usuarios", headers=sabor.h()).json())
    assert papeis == ["admin", "atendente", "cozinha"]
