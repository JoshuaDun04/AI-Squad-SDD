---
status: accepted
---
# Multi-restaurante em banco compartilhado com restaurante_id

Todos os restaurantes ficam no mesmo banco PostgreSQL e no mesmo schema; toda tabela de negócio tem `restaurante_id` NOT NULL, e o repositório da API sempre filtra pelo restaurante do usuário autenticado (RN-01). Escolhido porque o MVP precisa de custo e operação mínimos numa VPS; schema ou banco por restaurante multiplicam migrações e conexões sem ganho no volume esperado.

## Considered Options

- Banco por restaurante: isolamento físico, mas uma migração por cliente e custo de conexões.
- Schema por restaurante: meio-termo, mas migrações e pool ainda crescem por cliente.
- **Banco compartilhado + coluna (escolhido)**: barato; o risco de vazamento é tratado com filtro obrigatório no repositório e testes negativos de isolamento (BDD-ISO-*).

## Consequences

Uma consulta sem filtro vaza dados entre restaurantes, por isso nenhum endpoint acessa a sessão do banco diretamente: só via repositórios que recebem `restaurante_id`. Row-Level Security do PostgreSQL fica como reforço futuro.

## Implementação (Gate 3)

- `pdv_api/repositorios.py`: repositórios de negócio herdam de `_RepoDoRestaurante`, que exige `restaurante_id` no construtor. Exceções explícitas e documentadas: `RepoRestaurantes` e `RepoAutenticacao` (login por e-mail global).
- `pdv/api/scripts/verificar_rtm.py` falha o build se uma rota importar consultas do SQLAlchemy ou chamar a sessão direto, ou se um método de repositório do restaurante montar `select`/`delete` sem `self.rid`.
