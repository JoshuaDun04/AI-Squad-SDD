---
status: accepted
---
# Estoque como razão de movimentações com saldo materializado

Todo saldo de ingrediente nasce de movimentações (`saldo_inicial`, `entrada`, `ajuste`, `baixa_pedido`, `estorno_pedido`) gravadas numa tabela só de inserção. O saldo atual fica materializado em `ingrediente.saldo` e é atualizado na mesma transação da movimentação, que também grava `saldo_apos`. A aplicação nunca faz UPDATE nem DELETE em movimentações; erro de lançamento se corrige com novo ajuste (RN-17).

## Considered Options

- **Só o saldo, sem histórico:** simples, mas não responde "por que faltou tambaqui?", que é a dor DN-03.
- **Só o razão, saldo calculado por soma:** sempre consistente, mas cada leitura do cardápio do robô somaria o histórico inteiro.
- **Razão + saldo materializado (escolhido):** leitura barata e auditoria completa. O risco de divergência é coberto pelo cenário BDD-EXT-02 (soma do extrato = saldo).

## Consequences

- Toda escrita de estoque passa por um único serviço que trava a linha do ingrediente, grava a movimentação e atualiza o saldo.
- Para evitar deadlock entre um pedido que baixa vários ingredientes e uma entrada simultânea, as travas são sempre tomadas em ordem crescente de `ingrediente.id` (RT-10).
