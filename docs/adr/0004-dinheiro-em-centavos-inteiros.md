---
status: accepted
---
# Valores monetários em centavos inteiros

Preços, totais e troco são `int` em centavos (BRL) no domínio, no banco (`INTEGER`) e na API; a formatação "R$ 12,90" só acontece na borda (mensagens e painel). Evita erro de ponto flutuante e dispensa política de arredondamento na R1, já que não há divisão nem percentual (RN-02).

## Implementação (Gate 3)

A API recusa preço que não seja inteiro estrito (`12.90`, `"1290"` e `true` dão 422). O painel converte o texto digitado ("45,90") em centavos sem passar por ponto flutuante.
