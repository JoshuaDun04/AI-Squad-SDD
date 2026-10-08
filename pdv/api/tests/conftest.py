"""Infra de testes.

Banco: TEST_DATABASE_URL (ex.: postgresql+psycopg://pdv:pdv@localhost/pdv_test).
Sem a variável, usa SQLite em memória. A suíte roda nos dois.
"""

from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pdv_api.config import Config
from pdv_api.dominio.canal import CanalEmMemoria
from pdv_api.main import criar_app
from pdv_api.modelos import Base
from pdv_api.relogio import RelogioFixo
from pdv_api.seguranca import usar_hasher_rapido

usar_hasher_rapido()

MANAUS = ZoneInfo("America/Manaus")
JWT_SECRET = "segredo-de-teste-com-mais-de-32-caracteres!!"
GATEWAY_TOKEN = "token-gateway-teste-123"


def manaus(ano: int, mes: int, dia: int, hora: int = 12, minuto: int = 0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, tzinfo=MANAUS)


# terça-feira, 06/10/2026, 12:00 em Manaus
TERCA_MEIO_DIA = manaus(2026, 10, 6, 12, 0)


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        eng = create_engine(url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def _limpar_banco(engine):
    yield
    with engine.begin() as con:
        if engine.dialect.name == "postgresql":
            nomes = ", ".join(t.name for t in Base.metadata.sorted_tables)
            con.execute(text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))
        else:
            for t in reversed(Base.metadata.sorted_tables):
                con.execute(t.delete())


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo(TERCA_MEIO_DIA)


@pytest.fixture
def canal() -> CanalEmMemoria:
    return CanalEmMemoria()


@pytest.fixture
def config() -> Config:
    return Config(database_url="sqlite://", jwt_secret=JWT_SECRET, gateway_token=GATEWAY_TOKEN)


@pytest.fixture
def fabrica(engine):
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def client(config, canal, relogio, fabrica) -> TestClient:
    app = criar_app(config, canal_mensagens=canal, relogio=relogio, fabrica_sessao=fabrica)
    return TestClient(app)


_seq = itertools.count(1)


@dataclass
class Restaurante:
    """Atalhos para montar cenários BDD contra a API real."""

    client: TestClient
    nome: str
    id: str
    tokens: dict[str, str] = field(default_factory=dict)
    categorias: dict[str, str] = field(default_factory=dict)
    itens: dict[str, str] = field(default_factory=dict)

    def h(self, papel: str = "admin") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[papel]}"}

    def criar_usuario(self, papel: str, email: str | None = None, senha: str = "Senha#Forte1") -> str:
        email = email or f"{papel}{next(_seq)}@{self.nome.split()[0].lower()}.com"
        r = self.client.post("/usuarios", json={"email": email, "senha": senha, "papel": papel}, headers=self.h())
        assert r.status_code == 201, r.text
        login = self.client.post("/auth/login", json={"email": email, "senha": senha})
        assert login.status_code == 200, login.text
        self.tokens[papel] = login.json()["token"]
        return r.json()["id"]

    def categoria(self, nome: str, ordem: int = 0) -> str:
        r = self.client.post("/categorias", json={"nome": nome, "ordem": ordem}, headers=self.h())
        assert r.status_code == 201, r.text
        self.categorias[nome] = r.json()["id"]
        return r.json()["id"]

    def item(self, categoria: str, nome: str, preco: int, ordem: int = 0, disponivel: bool = True) -> str:
        r = self.client.post(
            "/itens",
            json={
                "categoria_id": self.categorias[categoria],
                "nome": nome,
                "preco_centavos": preco,
                "ordem": ordem,
                "disponivel": disponivel,
            },
            headers=self.h(),
        )
        assert r.status_code == 201, r.text
        self.itens[nome] = r.json()["id"]
        return r.json()["id"]

    def horarios(self, faixas: list[dict]) -> None:
        r = self.client.put("/horarios", json=faixas, headers=self.h())
        assert r.status_code == 200, r.text

    def aberto_sempre(self) -> None:
        self.horarios([{"dia_semana": d, "abre": "00:00", "fecha": "23:59"} for d in range(7)])

    def cardapio_padrao(self) -> None:
        """Peixes, Bebidas e Sobremesas, como nos cenários do bdd-r1.md."""
        self.categoria("Peixes", 1)
        self.categoria("Bebidas", 2)
        self.categoria("Sobremesas", 3)
        self.item("Peixes", "Tambaqui assado", 4590, 1)
        self.item("Peixes", "Pirarucu de casaca", 5290, 2)
        self.item("Bebidas", "Suco de cupuaçu", 890, 1)
        self.item("Bebidas", "Refrigerante lata", 600, 2)
        self.item("Sobremesas", "Pudim", 1200, 1)

    def msg(self, telefone: str, texto: str, mensagem_id: str | None = None, nome: str = "Maria") -> dict:
        r = self.client.post(
            "/canal/webhook",
            json={
                "tipo": "mensagem",
                "restaurante_id": self.id,
                "mensagem_id": mensagem_id or f"wamid-{next(_seq)}",
                "telefone": telefone,
                "nome_perfil": nome,
                "texto": texto,
                "recebida_em": "2026-10-06T12:00:00-04:00",
            },
            headers={"X-Gateway-Token": GATEWAY_TOKEN},
        )
        assert r.status_code == 200, r.text
        return r.json()

    def conversa(self, telefone: str, *textos: str) -> None:
        for t in textos:
            self.msg(telefone, t)

    def fila(self, papel: str = "cozinha") -> list[dict]:
        r = self.client.get("/fila", headers=self.h(papel))
        assert r.status_code == 200, r.text  # VAL-03: nunca contar itens de um corpo de erro
        return r.json()


@pytest.fixture
def novo_restaurante(client):
    def _criar(nome: str = "Sabor do Rio", email: str | None = None, senha: str = "Forte#2026") -> Restaurante:
        email = email or f"dono{next(_seq)}@{nome.split()[0].lower()}.com"
        r = client.post("/restaurantes", json={"nome": nome, "admin_email": email, "admin_senha": senha})
        assert r.status_code == 201, r.text
        login = client.post("/auth/login", json={"email": email, "senha": senha})
        assert login.status_code == 200, login.text
        return Restaurante(client, nome, r.json()["restaurante_id"], {"admin": login.json()["token"]})

    return _criar


@pytest.fixture
def sabor(novo_restaurante) -> Restaurante:
    """Restaurante A, aberto o dia todo, com cardápio padrão e equipe completa."""
    r = novo_restaurante("Sabor do Rio")
    r.aberto_sempre()
    r.cardapio_padrao()
    r.criar_usuario("atendente")
    r.criar_usuario("cozinha")
    return r


@pytest.fixture
def tacaca(novo_restaurante) -> Restaurante:
    """Restaurante B."""
    r = novo_restaurante("Tacacá da Praça")
    r.aberto_sempre()
    r.categoria("Tacacás")
    r.item("Tacacás", "Tacacá grande", 2500)
    r.criar_usuario("atendente")
    r.criar_usuario("cozinha")
    return r


CLIENTE = "5592991234567"


def fazer_pedido(rest: Restaurante, telefone: str = CLIENTE, entrega: bool = False) -> dict:
    """Pedido completo pelo robô: 2 × Tambaqui + 1 × Suco, Pix. Retorna o item da fila."""
    antes = {p["pedido_id"] for p in rest.fila()}
    rest.conversa(telefone, "oi", "1", "1", "2", "1", "2", "1", "1", "3")
    if entrega:
        rest.conversa(telefone, "2", "Rua 10 de Julho, 500, Centro", "1", "1")
    else:
        rest.conversa(telefone, "1", "1", "1")
    novos = [p for p in rest.fila() if p["pedido_id"] not in antes]
    assert len(novos) == 1, novos
    return novos[0]
