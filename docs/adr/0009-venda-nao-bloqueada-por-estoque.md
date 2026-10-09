---
status: proposed
---
# Venda não bloqueada por saldo, exceto em ingredientes marcados

Restaurantes pequenos raramente lançam todas as entradas na hora; bloquear vendas pelo saldo do sistema derrubaria pedidos que a cozinha consegue atender. Por isso a baixa pode deixar saldo negativo, e o painel destaca (RN-15). O admin pode marcar um ingrediente como "bloqueia venda" quando a falta é real e conhecida (ex.: polpa de fruta da estação); aí o item que o usa some do robô quando o saldo não cobre uma porção, pelo mesmo caminho da indisponibilidade da RN-04.

## Considered Options

- **Bloquear sempre:** estoque sempre "certo", mas vendas perdidas por cadastro desatualizado.
- **Nunca bloquear:** simples, mas o cliente pede o que não existe.
- **Bloqueio opcional por ingrediente (escolhido):** padrão permissivo e controle onde importa.

## Consequences

- A disponibilidade no robô passa a depender do saldo dos ingredientes marcados, calculada na mesma leitura do cardápio, sem job.
- Na confirmação, a regra é verificada de novo com as linhas travadas; se o saldo acabou entre o resumo e a confirmação, o pedido não é criado e a linha sai do carrinho com aviso (RN-04, BDD-BX-06).
