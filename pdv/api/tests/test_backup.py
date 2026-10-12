"""RF-24, RT-16 · BDD-BKP-*: banco local, backup e restauração (app Windows)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from pdv_api import ferramentas
from pdv_api.banco import criar_engine
from pdv_api.config import Config
from pdv_api.dominio.canal import CanalEmMemoria
from pdv_api.main import criar_app
from tests.conftest import GATEWAY_TOKEN, JWT_SECRET, Restaurante, fazer_pedido

RAIZ_API = Path(__file__).resolve().parents[1]


def _app_no_arquivo(banco: Path, relogio):
    engine = criar_engine(ferramentas.url_sqlite(banco))
    cfg = Config(database_url="sqlite://", jwt_secret=JWT_SECRET, gateway_token=GATEWAY_TOKEN, restaurante_unico=True)
    cliente = TestClient(
        criar_app(cfg, canal_mensagens=CanalEmMemoria(), relogio=relogio, fabrica_sessao=sessionmaker(engine, expire_on_commit=False))
    )
    return cliente, engine


def _montar_restaurante(cliente) -> Restaurante:
    r = cliente.post("/restaurantes", json={"nome": "Sabor do Rio", "admin_email": "dono@sabor.com", "admin_senha": "Forte#2026"})
    assert r.status_code == 201, r.text
    token = cliente.post("/auth/login", json={"email": "dono@sabor.com", "senha": "Forte#2026"}).json()["token"]
    rest = Restaurante(cliente, "Sabor do Rio", r.json()["restaurante_id"], {"admin": token})
    rest.aberto_sempre()
    rest.cardapio_padrao()
    rest.criar_usuario("cozinha")
    return rest


@pytest.mark.bdd("BDD-BKP-01")
def test_migrar_backup_e_restaurar_recuperam_os_dados(tmp_path, relogio):
    banco = tmp_path / "dados" / "pdv.sqlite"
    assert ferramentas.migrar(banco)["versao"] == "0005"
    cliente, engine = _app_no_arquivo(banco, relogio)
    rest = _montar_restaurante(cliente)
    pedido = fazer_pedido(rest)

    saida = ferramentas.backup(banco, tmp_path / "backups", motivo="diario")
    arquivo = Path(saida["arquivo"])
    assert arquivo.name.startswith("pdv-") and arquivo.name.endswith("-diario.sqlite")

    with sqlite3.connect(banco) as con:  # o banco "perde" os dados
        con.execute("PRAGMA foreign_keys=OFF")
        for tabela in ("pedido_item", "pedido", "item", "categoria"):
            con.execute(f"DELETE FROM {tabela}")
    engine.dispose()

    assert ferramentas.restaurar(banco, arquivo)["versao"] == "0005"
    cliente2, _ = _app_no_arquivo(banco, relogio)
    token = cliente2.post("/auth/login", json={"email": "dono@sabor.com", "senha": "Forte#2026"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert {i["nome"] for i in cliente2.get("/itens", headers=h).json()} >= {"Tambaqui assado", "Pudim"}
    assert cliente2.get(f"/pedidos/{pedido['pedido_id']}", headers=h).status_code == 200


@pytest.mark.bdd("BDD-BKP-01")
def test_backup_com_o_app_rodando_e_consistente(tmp_path, relogio):
    """A cópia é feita com conexões abertas e escrita em andamento (WAL)."""
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    cliente, _ = _app_no_arquivo(banco, relogio)
    rest = _montar_restaurante(cliente)
    fazer_pedido(rest)
    saida = ferramentas.backup(banco, tmp_path / "b")
    with sqlite3.connect(saida["arquivo"]) as con:
        assert con.execute("SELECT count(*) FROM pedido").fetchone()[0] == 1


@pytest.mark.bdd("BDD-BKP-02")
def test_guarda_so_os_mais_recentes(tmp_path):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    destino = tmp_path / "backups"
    base = datetime(2026, 10, 1, 3, 30)
    for i in range(16):
        ferramentas.backup(banco, destino, manter=100, motivo="diario", agora=base + timedelta(days=i))
    saida = ferramentas.backup(banco, destino, manter=14, motivo="manual", agora=base + timedelta(days=20))
    restantes = sorted(p.name for p in destino.glob("pdv-*.sqlite"))
    assert len(restantes) == 14
    assert restantes[-1] == "pdv-20261021-033000-manual.sqlite"
    assert "pdv-20261001-033000-diario.sqlite" not in restantes
    assert len(saida["removidos"]) == 3


@pytest.mark.bdd("BDD-BKP-03")
@pytest.mark.parametrize("conteudo", [b"isto nao e um banco", b"SQLite format 3\x00" + b"\x00" * 100, None])
def test_arquivo_invalido_e_recusado_sem_tocar_no_banco(tmp_path, conteudo):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    with sqlite3.connect(banco) as con:
        con.execute("INSERT INTO restaurante (id, nome, fuso) VALUES ('11111111111111111111111111111111', 'Sabor', 'America/Manaus')")
    falso = tmp_path / "falso.sqlite"
    if conteudo is None:  # banco SQLite válido, mas não é do PDV
        with sqlite3.connect(falso) as con:
            con.execute("CREATE TABLE outra (x)")
    else:
        falso.write_bytes(conteudo)
    with pytest.raises(ferramentas.ErroFerramenta):
        ferramentas.restaurar(banco, falso)
    with sqlite3.connect(banco) as con:
        assert con.execute("SELECT nome FROM restaurante").fetchone()[0] == "Sabor"


@pytest.mark.bdd("BDD-BKP-03")
def test_restaurar_arquivo_inexistente(tmp_path):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    with pytest.raises(ferramentas.ErroFerramenta, match="não encontrado"):
        ferramentas.restaurar(banco, tmp_path / "nao-existe.sqlite")


def test_linha_de_comando_responde_em_json(tmp_path):
    """É assim que o app Electron chama a ferramenta."""
    banco = tmp_path / "pdv.sqlite"

    def rodar(*args):
        r = subprocess.run(
            [sys.executable, "-m", "pdv_api.ferramentas", *args],
            cwd=RAIZ_API, capture_output=True, text=True, timeout=120,
        )
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])

    codigo, saida = rodar("migrar", "--banco", str(banco))
    assert codigo == 0 and saida == {"ok": True, "acao": "migrar", "versao": "0005"}
    codigo, saida = rodar("backup", "--banco", str(banco), "--destino", str(tmp_path / "b"), "--motivo", "saida")
    assert codigo == 0 and saida["arquivo"].endswith("-saida.sqlite")
    codigo, saida = rodar("restaurar", "--banco", str(banco), "--arquivo", str(tmp_path / "nada.sqlite"))
    assert codigo == 1 and saida == {"ok": False, "erro": "arquivo não encontrado"}
    codigo, saida = rodar("backup", "--banco", str(banco), "--destino", str(tmp_path / "b"), "--motivo", "../x")
    assert codigo == 1 and saida["erro"] == "motivo inválido"


def test_sqlite_do_app_usa_wal_e_chaves_estrangeiras(tmp_path):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    engine = criar_engine(ferramentas.url_sqlite(banco))
    with engine.connect() as con:
        assert con.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert con.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert con.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000


def test_api_sai_quando_o_app_fecha_a_entrada():
    """RT-19: a API do app Windows não fica órfã segurando o banco."""
    import io
    import threading

    from pdv_api.main import vigiar_processo_pai

    saiu = threading.Event()
    codigos: list[int] = []

    def sair(codigo: int) -> None:
        codigos.append(codigo)
        saiu.set()

    vigiar_processo_pai(io.BytesIO(b"x" * 3000), sair)
    assert saiu.wait(5)
    assert codigos == [0]


# ---------- RF-28 · senha do dono esquecida ----------


def _login(cliente, senha):
    return cliente.post("/auth/login", json={"email": "dono@sabor.com", "senha": senha})


def _cli_senha(banco: Path, email: str, senha: str):
    import os

    r = subprocess.run(
        [sys.executable, "-m", "pdv_api.ferramentas", "redefinir-senha", "--banco", str(banco), "--email", email],
        cwd=RAIZ_API, capture_output=True, text=True, timeout=120, env={**os.environ, "PDV_NOVA_SENHA": senha},
    )
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1]), r


@pytest.mark.bdd("BDD-SEN-01")
def test_dono_redefine_a_senha_no_computador(tmp_path, relogio):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    cliente, engine = _app_no_arquivo(banco, relogio)
    _montar_restaurante(cliente)
    for _ in range(3):
        assert _login(cliente, "errada-123").status_code == 401

    codigo, saida, proc = _cli_senha(banco, " Dono@Sabor.com ", "Nova#Senha2026")
    assert codigo == 0 and saida == {"ok": True, "acao": "redefinir-senha"}
    # A senha não aparece em lugar nenhum da saída
    assert "Nova#Senha2026" not in proc.stdout + proc.stderr

    assert _login(cliente, "Forte#2026").status_code == 401
    assert _login(cliente, "Nova#Senha2026").status_code == 200
    engine.dispose()


@pytest.mark.bdd("BDD-SEN-02")
def test_redefinir_senha_derruba_sessoes_abertas(tmp_path, relogio):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    cliente, engine = _app_no_arquivo(banco, relogio)
    rest = _montar_restaurante(cliente)
    antigo = {"Authorization": f"Bearer {rest.tokens['admin']}"}
    assert cliente.get("/relatorio", headers=antigo).status_code == 200

    ferramentas.redefinir_senha(banco, "dono@sabor.com", "Nova#Senha2026")
    assert cliente.get("/relatorio", headers=antigo).status_code == 401
    engine.dispose()


@pytest.mark.bdd("BDD-SEN-03")
def test_redefinir_senha_recusa_quem_nao_e_dono_e_senha_curta(tmp_path, relogio):
    banco = tmp_path / "pdv.sqlite"
    ferramentas.migrar(banco)
    cliente, engine = _app_no_arquivo(banco, relogio)
    rest = _montar_restaurante(cliente)
    rest.criar_usuario("atendente", email="caixa@sabor.com")

    codigo, saida, _ = _cli_senha(banco, "ninguem@sabor.com", "Nova#Senha2026")
    assert codigo == 1 and saida["erro"] == "nenhum administrador com esse e-mail"
    with pytest.raises(ferramentas.ErroFerramenta, match="administrador"):
        ferramentas.redefinir_senha(banco, "caixa@sabor.com", "Nova#Senha2026")
    codigo, saida, _ = _cli_senha(banco, "dono@sabor.com", "curta")
    assert codigo == 1 and "8 a 128" in saida["erro"]
    with pytest.raises(ferramentas.ErroFerramenta, match="banco não encontrado"):
        ferramentas.redefinir_senha(tmp_path / "outro.sqlite", "dono@sabor.com", "Nova#Senha2026")
    # nada mudou para o dono
    assert _login(cliente, "Forte#2026").status_code == 200
    engine.dispose()
