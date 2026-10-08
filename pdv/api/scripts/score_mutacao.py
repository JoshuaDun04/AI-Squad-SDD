#!/usr/bin/env python3
"""Lê `mutmut results --all true` e falha se o score ficar abaixo do mínimo.

Uso: mutmut results --all true | python scripts/score_mutacao.py --minimo 85 [--json saida.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minimo", type=float, default=85.0)
    ap.add_argument("--json")
    args = ap.parse_args()

    por_modulo: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for linha in sys.stdin:
        m = re.match(r"\s*pdv_api\.dominio\.(\w+)\.\S+: (.+)", linha)
        if m:
            por_modulo[m.group(1)][m.group(2).strip()] += 1

    total: collections.Counter = collections.Counter()
    saida = {}
    for modulo, c in sorted(por_modulo.items()):
        total.update(c)
        vivos = c["survived"] + c["timeout"]
        score = 100 * c["killed"] / max(1, c["killed"] + vivos)
        saida[modulo] = {**c, "score": round(score, 1)}
        print(f"{modulo:10} {score:6.1f}%  {dict(c)}")
    vivos = total["survived"] + total["timeout"]
    if total["killed"] + vivos == 0:
        print("nenhum mutante avaliado")
        return 1
    score = 100 * total["killed"] / (total["killed"] + vivos)
    saida["total"] = {**total, "score": round(score, 1)}
    print(f"{'TOTAL':10} {score:6.1f}%  (mínimo {args.minimo}%)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(saida, f, indent=2)
    return 0 if score >= args.minimo else 1


if __name__ == "__main__":
    sys.exit(main())
