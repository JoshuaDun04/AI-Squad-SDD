#!/usr/bin/env python3
"""Verificador de rastreabilidade e arquitetura da R1.

1. Cobertura BDD: todo cenário de docs/bdd-r1.md e docs/desktop/bdd-desktop.md tem ao menos um teste
   (pytest com @pytest.mark.bdd, ou teste do app em pdv/desktop/test com "[BDD-XXX-NN]" no título)
   marcado com @pytest.mark.bdd("<ID>") em pdv/api/tests/. Nenhum marcador
   aponta para cenário inexistente. Cenários @negative são listados à parte.
2. ADR-0001: nenhuma rota consulta o banco direto (sem select/query/execute/
   scalar/get na sessão dentro de pdv_api/rotas).
3. ADR-0001: todo método de repositório "do restaurante" que monta uma
   consulta usa self.rid.

Uso: python scripts/verificar_rtm.py [--raiz <repo>] [--json <saida>]
Sai com código 1 se houver violação.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve()
API = AQUI.parents[1]
RAIZ_PADRAO = AQUI.parents[3]

RE_CENARIO = re.compile(r"^@(BDD-[A-Z]+-\d+)\s+@(principal|variacao|negative)\b", re.M)
PROIBIDOS_NA_ROTA = {"query", "execute", "scalar", "scalars", "get", "add", "delete", "merge"}


def cenarios(bdd: Path) -> dict[str, str]:
    return dict(RE_CENARIO.findall(bdd.read_text(encoding="utf-8")))


def marcadores(tests: Path) -> dict[str, list[str]]:
    achados: dict[str, list[str]] = {}
    for arq in sorted(tests.glob("test_*.py")):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.FunctionDef) or not no.name.startswith("test_"):
                continue
            for dec in no.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "bdd"
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                ):
                    achados.setdefault(dec.args[0].value, []).append(f"{arq.name}::{no.name}")
    return achados


RE_ID_TITULO = re.compile(r"\[(BDD-[A-Z]+-\d+)\]")


def marcadores_desktop(pasta: Path) -> dict[str, list[str]]:
    """Testes do app Electron (node:test): o ID do cenário vai no título, ex.: "[BDD-PNL-01] ..."."""
    achados: dict[str, list[str]] = {}
    if not pasta.is_dir():
        return achados
    for arq in sorted(pasta.glob("*.test.*")):
        for ident in RE_ID_TITULO.findall(arq.read_text(encoding="utf-8")):
            achados.setdefault(ident, []).append(arq.name)
    return achados


def violacoes_rotas(rotas: Path) -> list[str]:
    erros = []
    for arq in sorted(rotas.glob("*.py")):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("sqlalchemy"):
                nomes = {a.name for a in no.names}
                if nomes - {"Session"}:
                    erros.append(f"{arq.name}:{no.lineno} importa {sorted(nomes)} de {no.module}")
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "sessao"
                and no.func.attr in PROIBIDOS_NA_ROTA
            ):
                erros.append(f"{arq.name}:{no.lineno} chama sessao.{no.func.attr}() direto")
    return erros


def violacoes_repositorios(repos: Path) -> list[str]:
    erros = []
    arvore = ast.parse(repos.read_text(encoding="utf-8"))
    for classe in [n for n in arvore.body if isinstance(n, ast.ClassDef)]:
        bases = {b.id for b in classe.bases if isinstance(b, ast.Name)}
        if "_RepoDoRestaurante" not in bases:
            continue
        for metodo in [n for n in classe.body if isinstance(n, ast.FunctionDef)]:
            fonte = ast.unparse(metodo)
            consulta = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"select", "delete"}
                for n in ast.walk(metodo)
            )
            if consulta and "self.rid" not in fonte:
                erros.append(f"{classe.name}.{metodo.name} consulta sem filtrar por self.rid")
    return erros


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    todos = cenarios(args.raiz / "docs" / "bdd-r1.md")
    todos.update(cenarios(args.raiz / "docs" / "desktop" / "bdd-desktop.md"))
    marcas = marcadores(API / "tests")
    for ident, testes in marcadores_desktop(args.raiz / "pdv" / "desktop" / "test").items():
        marcas.setdefault(ident, []).extend(testes)
    sem_teste = sorted(c for c in todos if c not in marcas)
    orfaos = sorted(m for m in marcas if m not in todos)
    negativos = sorted(c for c, t in todos.items() if t == "negative")
    rotas = violacoes_rotas(API / "pdv_api" / "rotas")
    repos = violacoes_repositorios(API / "pdv_api" / "repositorios.py")

    relatorio = {
        "cenarios": len(todos),
        "cenarios_cobertos": len(todos) - len(sem_teste),
        "negativos": len(negativos),
        "negativos_cobertos": len([n for n in negativos if n in marcas]),
        "sem_teste": sem_teste,
        "marcadores_orfaos": orfaos,
        "violacoes_rotas": rotas,
        "violacoes_repositorios": repos,
        "mapa": {c: marcas.get(c, []) for c in sorted(todos)},
    }
    ok = not (sem_teste or orfaos or rotas or repos)
    relatorio["status"] = "PASSED" if ok else "FAILED"

    print(f"Cenários BDD: {relatorio['cenarios_cobertos']}/{relatorio['cenarios']} cobertos")
    print(f"Negativos:    {relatorio['negativos_cobertos']}/{relatorio['negativos']} cobertos")
    for rotulo, lista in (
        ("Sem teste", sem_teste),
        ("Marcador órfão", orfaos),
        ("Rota acessa banco", rotas),
        ("Repositório sem filtro", repos),
    ):
        for item in lista:
            print(f"  ✗ {rotulo}: {item}")
    print(relatorio["status"])
    if args.json:
        args.json.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
