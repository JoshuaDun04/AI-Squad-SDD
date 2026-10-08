# Parecer do Gate 4 — PDV Restaurantes R1

- Data: 08/10/2026 · Estado técnico: **ready, com uma pendência de infraestrutura** (build das imagens Docker não executado neste ambiente)
- Base: código construído do zero nesta data. O parecer anterior (06/10/2026, candidato `2855b6ada300304b`) foi **descartado**: citava 82 testes e mutação executados, mas não havia repositório correspondente.
- Validador: mesmo agente que implementou (revisão sequencial, não independente)

## Evidências

Arquivos em `docs/evidence/`.

| Verificação | Resultado | Como reproduzir |
|---|---|---|
| pytest da API em **PostgreSQL 16** | 268 passed | `TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest` (`pytest-postgres.xml`) |
| pytest da API em SQLite | 268 passed | `python -m pytest` (`pytest-sqlite.xml`) |
| Cobertura de linhas da API | 98% | `--cov=pdv_api` |
| Verificador de RTM e arquitetura | PASSED · 38/38 cenários, 19/19 negativos cobertos · 0 violações da ADR-0001 | `python scripts/verificar_rtm.py` (`rtm.json`) |
| Mutação nos módulos de regra (mutmut 3) | **98,1%** (944 mortos, 18 sobreviventes) · status 100 · dinheiro 100 · canal 100 · robô 98,2 · horário 96,3 · LGPD 95,2 | `mutmut run` (`mutacao.json`) |
| Migrações Alembic | `upgrade`, `downgrade base`, `upgrade` e `alembic check` sem divergência, em PostgreSQL | `alembic check` |
| Gateway (node:test) | 12 pass | `npm test` em `pdv/wa-gateway` |
| Painel (vitest) | 5 pass · build de produção ok | `npm test && npm run build` em `pdv/web` |
| E2E no navegador (Playwright, Chromium) | ok: cadastro → cardápio → horários → equipe → 2 pedidos via webhook → fila em **1,9 s** → preparo/pronto → detalhe com endereço → cancelamento → celular 390 px sem rolagem horizontal | API + gateway + painel rodando localmente sobre PostgreSQL |
| Logs reais do e2e | nenhum telefone nem endereço em `api.log` e `gw.log`; falhas de envio aparecem como `*****-4567` | varredura com grep |
| Auditoria de dependências | 0 vulnerabilidades (pip-audit no lock da API; npm audit no gateway e no painel) | PyJWT atualizado para 2.15.1 e vitest para 5 durante a auditoria |

### Critérios de sucesso da R1 (PRD §7)

1. Pedido completo pelo robô sem intervenção humana, visível na cozinha em até 5 s: ✅ 1,9 s no e2e (polling de 3 s).
2. Mudança de status gera aviso ao cliente: ✅ BDD-COZ-01 (aviso a cada mudança) e BDD-CAN-01. ⚠️ No e2e, o envio real falhou de propósito (sem sessão de WhatsApp) e o status mudou mesmo assim, como previsto.
3. Testes de isolamento entre restaurantes: ✅ BDD-ISO-01..03, mais isolamento no webhook e na numeração.
4. Verificador sem negativo órfão e mutação ≥ 85%: ✅ 19/19 e 98,1%.

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

## Limitações declaradas

- **Imagens Docker não construídas**: o registro do Docker Hub está bloqueado neste ambiente. `docker compose config` valida o arquivo; os três Dockerfiles não foram executados. É a primeira coisa a rodar na VPS.
- **WhatsApp real não testado**: a conexão do Baileys com os servidores do WhatsApp não sai deste ambiente, então QR code, envio e recebimento reais não foram exercitados. O gateway foi testado com sessões falsas e o fluxo completo da API com webhook simulado.
- Baileys 7 ainda é release candidate. Contatos que chegam só com identificador LID recebem respostas, mas, depois de reiniciar o gateway, avisos de status para eles só voltam quando o cliente mandar nova mensagem.
- Sem reenvio automático de aviso que falhou (previsto para R3 no bdd-r1).
- O verificador AST cobre só a API Python.
- Revisão sequencial pelo mesmo agente.

## Para fechar o Gate 4 na VPS

1. `docker compose up -d --build` com o `.env` preenchido.
2. Conectar um número de teste pelo QR code e fazer um pedido real de ponta a ponta.
3. Conferir `docker compose logs api wa-gateway` sem telefone nem endereço.
