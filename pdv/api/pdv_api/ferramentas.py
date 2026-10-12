"""Ferramentas de manutenção do banco local, chamadas pelo app Windows (RF-24, RT-16).

    python -m pdv_api.ferramentas migrar   --banco C:\\...\\pdv.sqlite
    python -m pdv_api.ferramentas backup   --banco ... --destino C:\\...\\backups [--manter 14] [--motivo diario]
    python -m pdv_api.ferramentas restaurar --banco ... --arquivo C:\\...\\backups\\pdv-....sqlite
    python -m pdv_api.ferramentas redefinir-senha --banco ... --email dono@...   (senha nova em PDV_NOVA_SENHA)

Cada comando imprime uma linha JSON com o resultado; sai com código 1 em erro.
O app para a API e o gateway antes de restaurar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ_API = Path(__file__).resolve().parents[1]
PREFIXO = "pdv-"
SUFIXO = ".sqlite"
TABELAS_OBRIGATORIAS = {"alembic_version", "restaurante", "pedido", "item"}
_RE_MOTIVO = re.compile(r"^[a-z0-9-]{1,20}$")


class ErroFerramenta(Exception):
    pass


def url_sqlite(banco: Path) -> str:
    return f"sqlite:///{banco.resolve().as_posix()}"


def migrar(banco: Path) -> dict:
    """Aplica as migrações Alembic no arquivo (cria o banco na primeira execução)."""
    from alembic import command
    from alembic.config import Config as ConfigAlembic

    banco.parent.mkdir(parents=True, exist_ok=True)
    cfg = ConfigAlembic(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "migracoes"))
    cfg.set_main_option("sqlalchemy.url", url_sqlite(banco))
    anterior = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url_sqlite(banco)
    try:
        command.upgrade(cfg, "head")
    finally:
        if anterior is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = anterior
    return {"ok": True, "acao": "migrar", "versao": versao(banco)}


def versao(banco: Path) -> str | None:
    with sqlite3.connect(banco) as con:
        try:
            linha = con.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.DatabaseError:
            return None
    return linha[0] if linha else None


def validar(arquivo: Path) -> None:
    """Recusa o que não for um banco íntegro do PDV (BDD-BKP-03)."""
    if not arquivo.is_file():
        raise ErroFerramenta("arquivo não encontrado")
    with arquivo.open("rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise ErroFerramenta("o arquivo não é um backup do PDV")
    con = sqlite3.connect(f"file:{arquivo.resolve().as_posix()}?mode=ro", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ErroFerramenta("o backup está corrompido")
        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as exc:
        raise ErroFerramenta("o arquivo não é um backup do PDV") from exc
    finally:
        con.close()
    if not TABELAS_OBRIGATORIAS <= tabelas:
        raise ErroFerramenta("o arquivo não é um backup do PDV")


def backup(banco: Path, destino: Path, manter: int = 14, motivo: str = "manual", agora: datetime | None = None) -> dict:
    """Cópia consistente pela API de backup do SQLite, com o app rodando (ADR-0012)."""
    if not banco.is_file():
        raise ErroFerramenta("banco não encontrado")
    if not _RE_MOTIVO.match(motivo):
        raise ErroFerramenta("motivo inválido")
    if manter < 1:
        raise ErroFerramenta("manter deve ser pelo menos 1")
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = (agora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    arquivo = destino / f"{PREFIXO}{carimbo}-{motivo}{SUFIXO}"
    temporario = arquivo.with_suffix(".parcial")
    origem = sqlite3.connect(banco, timeout=10)
    copia = sqlite3.connect(temporario)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    os.replace(temporario, arquivo)
    validar(arquivo)
    removidos = limpar_antigos(destino, manter)
    return {"ok": True, "acao": "backup", "arquivo": str(arquivo), "bytes": arquivo.stat().st_size, "removidos": removidos}


def limpar_antigos(destino: Path, manter: int) -> list[str]:
    backups = sorted(destino.glob(f"{PREFIXO}*{SUFIXO}"), key=lambda p: p.name, reverse=True)
    removidos = []
    for antigo in backups[manter:]:
        antigo.unlink()
        removidos.append(antigo.name)
    return removidos


def restaurar(banco: Path, arquivo: Path) -> dict:
    """Substitui o banco pelo backup. O banco atual só é tocado depois que o backup é validado."""
    validar(arquivo)
    banco.parent.mkdir(parents=True, exist_ok=True)
    temporario = banco.with_suffix(".restaurando")
    origem = sqlite3.connect(f"file:{arquivo.resolve().as_posix()}?mode=ro", uri=True)
    copia = sqlite3.connect(temporario)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    for extra in (banco.with_name(banco.name + "-wal"), banco.with_name(banco.name + "-shm")):
        extra.unlink(missing_ok=True)
    os.replace(temporario, banco)
    resultado = migrar(banco)  # backup de versão anterior sobe para o esquema atual
    return {"ok": True, "acao": "restaurar", "arquivo": str(arquivo), "versao": resultado["versao"]}


def redefinir_senha(banco: Path, email: str, senha: str) -> dict:
    """Senha do dono esquecida: quem está no computador do restaurante define outra.

    Só para administradores. Derruba as sessões abertas (sessao_versao) e zera o limite de tentativas.
    A senha chega por variável de ambiente, nunca na linha de comando (ficaria na lista de processos).
    """
    from sqlalchemy import delete, select
    from sqlalchemy.orm import Session

    from pdv_api import modelos as m
    from pdv_api.banco import criar_engine
    from pdv_api.rotas.auth import SENHA_MIN
    from pdv_api.seguranca import hash_senha

    if not banco.exists():
        raise ErroFerramenta("banco não encontrado")
    if not (SENHA_MIN <= len(senha) <= 128):
        raise ErroFerramenta(f"a senha precisa ter de {SENHA_MIN} a 128 caracteres")
    email = email.strip().lower()
    engine = criar_engine(url_sqlite(banco))
    try:
        with Session(engine) as sessao, sessao.begin():
            usuario = sessao.scalars(select(m.Usuario).where(m.Usuario.email == email)).first()
            if usuario is None or usuario.papel != "admin":
                raise ErroFerramenta("nenhum administrador com esse e-mail")
            usuario.senha_hash = hash_senha(senha)
            usuario.sessao_versao += 1
            usuario.ativo = True
            sessao.execute(delete(m.TentativaLogin).where(m.TentativaLogin.chave.like(f"{email}|%")))
    finally:
        engine.dispose()
    return {"ok": True, "acao": "redefinir-senha"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pdv_api.ferramentas")
    sub = ap.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("migrar")
    m.add_argument("--banco", type=Path, required=True)
    b = sub.add_parser("backup")
    b.add_argument("--banco", type=Path, required=True)
    b.add_argument("--destino", type=Path, required=True)
    b.add_argument("--manter", type=int, default=14)
    b.add_argument("--motivo", default="manual")
    r = sub.add_parser("restaurar")
    r.add_argument("--banco", type=Path, required=True)
    r.add_argument("--arquivo", type=Path, required=True)
    s = sub.add_parser("redefinir-senha")
    s.add_argument("--banco", type=Path, required=True)
    s.add_argument("--email", required=True)
    args = ap.parse_args(argv)
    try:
        if args.comando == "migrar":
            saida = migrar(args.banco)
        elif args.comando == "backup":
            saida = backup(args.banco, args.destino, args.manter, args.motivo)
        elif args.comando == "redefinir-senha":
            saida = redefinir_senha(args.banco, args.email, os.environ.get("PDV_NOVA_SENHA", ""))
        else:
            saida = restaurar(args.banco, args.arquivo)
    except ErroFerramenta as exc:
        print(json.dumps({"ok": False, "erro": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001 - nunca imprime traceback com dados (RN-10)
        print(json.dumps({"ok": False, "erro": f"falha inesperada: {type(exc).__name__}"}, ensure_ascii=False))
        return 1
    print(json.dumps(saida, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
