---
status: accepted
---
# Quantidades de estoque em inteiros na unidade base (g, ml, un)

Como o dinheiro em centavos (ADR-0004), quantidades de estoque são inteiros numa unidade base escolhida no cadastro do ingrediente: grama, mililitro ou unidade. O painel aceita "kg" e "L" na digitação e converte na borda (×1000). Não há conversão entre unidades diferentes do mesmo ingrediente na R2.

## Consequences

- Sem erro de ponto flutuante na baixa (400 g × 3 = 1200 g exatos) nem política de arredondamento.
- A unidade não muda depois que o ingrediente é criado, para não reinterpretar o histórico.
- Ingredientes vendidos em frações menores que 1 g (ex.: açafrão) ficam com resolução de 1 g; aceitável para o público da R2.
