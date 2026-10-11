# Parecer do Gate 4 — PDV Restaurantes R1

- Data: 08/10/2026, atualizado em 09/10/2026 · Estado técnico: **ready**. Pendência de ambiente: WhatsApp real (ver Limitações). Imagens Docker construídas e testadas no CI em 11/10/2026.
- Base: código construído do zero em 08/10/2026. O parecer anterior (06/10/2026, candidato `2855b6ada300304b`) foi **descartado**: citava 82 testes e mutação executados, mas não havia repositório correspondente.
- Validação: **revisão independente** por um agente que não participou da construção, com duas rodadas de reverificação das correções. 25 achados (REV-01..REV-25), todos fechados.

## Evidências

Arquivos em `docs/evidence/`.

| Verificação | Resultado (09/10/2026) | Como reproduzir |
|---|---|---|
| pytest da API em **PostgreSQL 16** | 312 passed | `TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest` (`pytest-postgres.xml`) |
| pytest da API em SQLite | 308 passed, 4 skipped (testes de concorrência que exigem PostgreSQL) | `python -m pytest` (`pytest-sqlite.xml`) |
| Cobertura de linhas da API | 99% | `--cov=pdv_api` |
| Verificador de RTM e arquitetura | PASSED · 43/43 cenários, 22/22 negativos cobertos · 0 violações da ADR-0001 | `python scripts/verificar_rtm.py` (`rtm.json`) |
| Mutação nos módulos de regra (mutmut 3) | **98,4%** (1086 mortos, 18 sobreviventes) · status 100 · dinheiro 100 · canal 100 · robô 98,5 · horário 96,3 · LGPD 95,2 | `mutmut run` (`mutacao.json`) |
| Migrações Alembic (0001..0004) | `upgrade`, `check`, `downgrade base`, `upgrade` sem divergência, em PostgreSQL | `alembic check` |
| Gateway (node:test) | 16 pass · `tsc` sem erros | `npm test` em `pdv/wa-gateway` |
| Painel (vitest) | 6 pass · build de produção ok | `npm test && npm run build` em `pdv/web` |
| nginx do painel | `nginx -t` ok com o arquivo gerado de `PROXY_CONFIAVEL`; valor que não seja IP/CIDR é recusado | `entrypoint/05-proxy-confiavel.sh` |
| E2E no navegador (Playwright, Chromium) | ok (08/10): cadastro → cardápio → horários → equipe → pedidos via webhook → fila em **1,9 s** → preparo/pronto → cancelamento → celular 390 px | capturas em `evidence/e2e/` |
| Auditoria de dependências | 0 vulnerabilidades (pip-audit com hashes; npm audit no gateway e no painel) | job `api` do CI |
| CI (GitHub Actions) | **sucesso no run #1 (11/10/2026, commit 3533ec4)**: API em PostgreSQL + migrações + RTM + auditoria (1m23s), mutação ≥ 85% (4m19s), gateway, painel, **build das 3 imagens Docker e e2e contra o compose** (1m37s) | [JoshuaDun04/AI-Squad-SDD, run 38102495174](https://github.com/JoshuaDun04/AI-Squad-SDD/actions/runs/38102495174) |

### Critérios de sucesso da R1 (PRD §7)

1. Pedido completo pelo robô sem intervenção humana, visível na cozinha em até 5 s: ✅ 1,9 s no e2e (polling de 3 s).
2. Mudança de status gera aviso ao cliente: ✅ BDD-COZ-01 (aviso a cada mudança) e BDD-CAN-01. ⚠️ No e2e, o envio real falhou de propósito (sem sessão de WhatsApp) e o status mudou mesmo assim, como previsto.
3. Testes de isolamento entre restaurantes: ✅ BDD-ISO-01..03, mais isolamento no webhook e na numeração.
4. Verificador sem negativo órfão e mutação ≥ 85%: ✅ 22/22 e 98,4%.

### Sobreviventes da mutação (18)

Todos revisados. São equivalentes ou redundantes de propósito:

- Limpezas defensivas em `conversa.dados` (`pop` de `item_id`, `item_nome`, `endereco`, `troco_para`), já cobertas por outra regra: o pedido só lê `endereco` se for entrega e `troco_para` se for dinheiro.
- `range(0, 8)` ↔ `range(8)` e `range(0, 9)` em `proxima_abertura`: mesmo resultado com uma faixa por dia.
- `return True` no ramo de exceção do filtro de log (registro malformado; não reproduzível sem forçar erro interno do `logging`).
- `respostas +=` ↔ `respostas =` nos menus de tipo e pagamento: a lista está sempre vazia nesses estados.

## Achados e correções durante a construção

| ID | Impacto | Achado | Fechamento |
|---|---|---|---|
| IMP-01 | high | Relógio de teste em fuso local gravado sem fuso no SQLite fazia a conversa "expirar" na hora | Relógio sempre em UTC; datas lidas do banco normalizadas (`em_utc`) |
| IMP-02 | medium | Dois atendentes podiam aplicar a mesma transição ao mesmo tempo | Linha do pedido travada com `SELECT ... FOR UPDATE` na troca de status e no cancelamento |
| IMP-03 | medium | Limite de login em memória zerava ao reiniciar | Tentativas persistidas na tabela `tentativa_login` |
| IMP-04 | low | Ramos inalcançáveis no robô (carrinho vazio na confirmação, item sumido na quantidade) | Removidos, com comentário da garantia que os torna impossíveis |
| IMP-05 | low | Fonte do painel vinha do Google Fonts (dependência externa e coleta de IP do cliente) | Fonte embutida no build (`@fontsource-variable/archivo`) |
| SEC-01..03 | — | Força bruta no login, CORS aberto, segredos padrão | Implementados desde o início: 429 após 5 falhas/15 min, CORS desligado por padrão, API e gateway recusam iniciar com segredos curtos (testes em `test_config.py` e `gateway.test.ts`) |
| SEC-04 | low | O webhook do gateway ficaria exposto pelo painel | nginx do painel responde 404 em `/api/canal/` |

## Revisão independente (REV-01..REV-25)

Um agente sem acesso ao histórico da construção revisou código, testes e documentos contra PRD, RTM, BDD e contratos. Depois, outros agentes reverificaram as correções em duas rodadas: a primeira encontrou REV-18..22, a segunda REV-23..25. Todos os achados estão corrigidos e cobertos por teste.

| ID | Impacto | Achado | Correção |
|---|---|---|---|
| REV-01/02 | high | Duas mensagens simultâneas do mesmo cliente corrompiam a conversa; erro 500 vazava traceback | Conversa travada por cliente; cliente, conversa e mensagem com `ON CONFLICT`; 500 genérico; `hide_parameters`; log do Postgres em modo terse |
| REV-04 | high | Numeração diária podia repetir sob concorrência | Tabela `contador_pedido` com incremento atômico (migração 0003) |
| REV-05/06 | high | Escolha numérica resolvida contra o cardápio atual, não o exibido; confirmação podia cobrar total diferente do resumo | Escolhas resolvidas pelo menu mostrado; confirma só o total exibido (BDD-ROB-07, BDD-PED-07) |
| REV-07 | medium | Limite de login contornável trocando de IP ou atrás de proxy | Limite por e-mail+IP real e por IP; nginx fixa `X-Forwarded-For` |
| REV-08 | medium | Isolamento testado só por rota | Teste por método de repositório (`test_isolamento_repos.py`) |
| REV-09/12 | medium | Logs do Baileys com JIDs e telefone; JSON inválido virava 500 no gateway | Máscara profunda nos logs do Baileys; 400/413 |
| REV-10 | medium | Status da conexão WhatsApp regredia ou mostrava "desconectado" sem confirmação | Estado só muda com confirmação do gateway |
| REV-11 | low | Filtro de log mascarava trechos de UUID | Regex com fronteiras; UUIDs intactos |
| REV-13 | medium | Token continuava válido após troca de senha ou papel | `sessao_versao` invalida tokens emitidos |
| REV-14 | low | Dependências sem hash | Lock com hashes (`--require-hashes`) |
| REV-15/16/17 | low | Testes faltantes; sem CSP; hora no fuso do aparelho; conversas antigas guardadas para sempre | Testes, CSP no nginx, data e hora no fuso do restaurante, limpeza de conversas paradas há 24 h |
| REV-18/19 | medium | IP real do cliente aceito de qualquer origem | nginx usa `realip` só do proxy em `PROXY_CONFIAVEL`; API confia só em redes privadas do Docker |
| REV-20/21 | low | Filtros sem teste de defesa em profundidade; máscara apagava datas | Testes dos filtros; máscara só em 10 a 15 dígitos |
| REV-22 | low | Limpeza de conversas sem índice e com risco de travar | Índice, lotes de 100, `SKIP LOCKED` (migração 0004) |
| REV-23 | low | Telefone formatado ("(92) 99123-4567") escapava da segunda barreira de log | Regex cobre formatos com espaço, parênteses e hífen |
| REV-24 | low | `PROXY_CONFIAVEL` aceitava só uma rede | Lista de redes; entrypoint gera um `set_real_ip_from` por rede e recusa valor inválido |
| REV-25 | low | Limpeza processava um só lote por mensagem | Repete os lotes até esvaziar (limite de 20 por mensagem) |

## Pendências da squad resolvidas em 08–09/10/2026

- **DEC-07 (observação livre):** por pedido na R1 (RN-11, BDD-OBS-01..03, migração 0002); por item adiada para a R2. Ver [decisoes.md](decisoes.md).
- **Contatos LID:** o gateway grava o endereço de resposta por restaurante no volume de dados; depois de reiniciar, os avisos continuam chegando. Apagado ao desconectar o número.
- **CI:** publicado no GitHub; primeira execução verde em 11/10/2026.

## Limitações declaradas

- **WhatsApp real não testado**: a conexão do Baileys com os servidores do WhatsApp não sai deste ambiente. QR code, envio e recebimento reais ficam para a VPS.
- Baileys 7 ainda é release candidate.
- Sem reenvio automático de aviso que falhou (previsto para R3).
- O verificador AST cobre só a API Python.

## Para fechar o Gate 4 na VPS

1. `docker compose up -d --build` com o `.env` preenchido.
2. Conectar um número de teste pelo QR code e fazer um pedido real de ponta a ponta.
3. Conferir `docker compose logs api wa-gateway` sem telefone nem endereço.
