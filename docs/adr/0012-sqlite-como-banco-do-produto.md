---
status: accepted
---
# SQLite como banco do produto

Com um restaurante por instalação (DEC-11), o volume é de dezenas a poucas centenas de pedidos por dia. O SQLite atende sem instalar nada e cabe num arquivo que o backup copia por inteiro.

## Configuração obrigatória

- `journal_mode=WAL` (leituras não bloqueiam escritas), `foreign_keys=ON`, `busy_timeout=5000`.
- Toda transação começa com `BEGIN IMMEDIATE`: as escritas ficam em série, o que substitui o `SELECT ... FOR UPDATE` e o `SKIP LOCKED` do PostgreSQL (que o SQLite ignora) sem corrida entre mensagens simultâneas.
- As migrações Alembic são as mesmas; o CI aplica e confere todas num arquivo SQLite.
- Backup pela API de backup do SQLite (cópia consistente com o app rodando), nunca copiando o arquivo aberto.

## Consequences

- O relatório do piloto deixa de usar `percentile_cont` do PostgreSQL e passa a ser calculado em Python, portável.
- O suporte a PostgreSQL continua no código e nos testes do CI, sem uso no produto.
