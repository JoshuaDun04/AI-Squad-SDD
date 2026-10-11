---
status: accepted
---
# Linha de pedido com variação, adicionais, observação e consumo congelados

A partir da R2, uma linha do carrinho e do pedido é identificada por item, opção de variação, conjunto de adicionais e observação; duas escolhas só somam quantidade quando os quatro coincidem (RN-22). Na confirmação, o pedido congela nomes, preço unitário (preço da opção ou do item, mais adicionais) e o consumo de ingredientes calculado pela ficha vigente, gravado em `consumo_pedido`.

## Consequences

- O estorno (RN-16) devolve o consumo congelado, não a ficha atual (BDD-EST-02).
- Pedidos da R1 continuam válidos: as colunas novas de `pedido_item` são opcionais e `consumo_pedido` fica vazio para eles.
- O robô ganha os estados VARIACAO, ADICIONAIS e de observação por item; as escolhas continuam resolvidas pelo menu exibido (REV-05).
