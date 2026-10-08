---
status: accepted
---
# Migrações versionadas com Alembic e testes em PostgreSQL

O esquema do banco é criado e evoluído por migrações Alembic (`pdv/api/migracoes/`), aplicadas pelo contêiner da API antes de subir (`alembic upgrade head`). A API nunca chama `create_all` em produção. A suíte de testes roda em PostgreSQL (variável `TEST_DATABASE_URL`) e também em SQLite para desenvolvimento rápido.

## Consequences

- Toda mudança de modelo exige nova migração; `alembic check` acusa divergência entre modelos e migrações.
- O limite de tentativas de login é persistido na tabela `tentativa_login`: sobrevive a reinício e vale entre réplicas.
- A troca de status trava a linha do pedido (`SELECT ... FOR UPDATE`), então dois atendentes não aplicam a mesma transição.
