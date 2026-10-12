---
status: accepted
---
# Monorepo com governança SDD na raiz e verificação por workspace

O código fica em `pdv/` (`api/` Python, `wa-gateway/` TS, `web/` React TS e, desde a DEC-11, `desktop/` com o app Windows em Electron) e a governança da squad em `docs/` na raiz.

## Revisão no Gate 3 (08/10/2026)

O projeto começou do zero, sem a ferramenta de verificação da squad disponível. Em vez do workspace temporário com symlinks, a verificação passou a ser um script do próprio repositório: `pdv/api/scripts/verificar_rtm.py` lê `docs/bdd-r1.md`, confere que cada cenário tem teste marcado com `@pytest.mark.bdd("<ID>")` e aplica as regras de arquitetura da ADR-0001. O gateway (node:test) e o painel (vitest + e2e Playwright) têm testes próprios, fora do verificador.


## Revisão na DEC-11 (12/10/2026)

O Docker Compose saiu do repositório junto com a implantação em servidor. O verificador passou a ler também `docs/desktop/bdd-desktop.md`; cenários do app Electron são conferidos pelo ID no título dos testes de `pdv/desktop/test` (node:test).
