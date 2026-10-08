---
status: accepted
---
# Migrações versionadas com Alembic e testes em PostgreSQL

O esquema do banco é criado e evoluído por migrações Alembic (`pdv/api/migracoes/`), aplicadas pelo contêiner da API antes de subir (`alembic upgrade head`). A API nunca chama `create_all` em produção. A suíte de testes roda em PostgreSQL (variável `TEST_DATABASE_URL`) e também em SQLite para desenvolvimento rápido.

## Consequences

- Toda mudança de modelo exige nova migração; `alembic check` acusa divergência entre modelos e migrações.
- O limite de tentativas de login é persistido na tabela `tentativa_login`: sobrevive a reinício e vale entre réplicas.
- A troca de status trava a linha do pedido (`SELECT ... FOR UPDATE`), então dois atendentes não aplicam a mesma transição.

## Revisão após a auditoria independente (08/10/2026)

- **Concorrência no robô:** cada mensagem trava a linha da conversa do cliente (`SELECT ... FOR UPDATE`) até o commit. Cliente, conversa e `mensagem_processada` são criados com `INSERT ... ON CONFLICT DO NOTHING`, sem corrida.
- **Numeração:** a tabela `contador_pedido` recebe incremento atômico (`INSERT ... ON CONFLICT DO UPDATE ... RETURNING`), em vez de `max()+1` com novas tentativas. A migração 0003 preenche o contador a partir dos pedidos existentes.
- **Logs:** o motor do SQLAlchemy usa `hide_parameters=True`; exceções não tratadas viram 500 com só o tipo no log; o PostgreSQL do compose roda com `log_error_verbosity=terse`.
- Os testes de concorrência (`tests/test_concorrencia.py`) só rodam em PostgreSQL, que é o banco do CI.
