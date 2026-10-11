# Contratos — Fatia R2

- Fonte: RTM-r2.md, ADR-0007..0010 · Convenções da R1 mantidas: JSON UTF-8, centavos `int`, quantidades de estoque `int` na unidade base, ids UUID, erros `{"erro","detalhe"}`, recurso de outro restaurante → **404**
- Papéis: **A** admin · **T** atendente · **C** cozinha

## 1. Ingredientes e estoque

| Método e rota | Papéis | Corpo / retorno | Erros | Requisitos |
|---|---|---|---|---|
| `GET /ingredientes?situacao=alerta\|negativo\|todos&incluir_inativos=false` | A, T, C | `[{id, nome, unidade, saldo, estoque_minimo, bloqueia_venda, ativo, situacao: "ok"\|"abaixo_minimo"\|"negativo"}]`, ordenado por criticidade quando `situacao=alerta` | — | RF-17, RN-18 |
| `GET /ingredientes/alertas/contagem` | A, T, C | `{abaixo_minimo, negativo}` (para o contador do painel; polling de 30 s) | — | RF-17 |
| `POST /ingredientes` | A | `{nome, unidade: "g"\|"ml"\|"un", estoque_minimo>=0, bloqueia_venda, saldo_inicial>=0}` → `201` | 403, 409 nome repetido, 422 | RF-12, RN-12 |
| `PATCH /ingredientes/{id}` | A | `{nome?, estoque_minimo?, bloqueia_venda?, ativo?}` (unidade não muda depois de criado) | 403, 404, 409, 422 | RF-12 |
| `POST /estoque/entradas` | A | `{referencia?, itens: [{ingrediente_id, quantidade>0}]}` → `201 {movimentacoes: [...]}`; tudo ou nada | 403 (T, C), 404, 422 | RF-14, RN-17, RN-23 |
| `POST /estoque/inventario` | A | `{ingrediente_id, contagem>=0, motivo (3..300)}` → `201 {movimentacao}`; diferença zero não cria movimentação (`200 {movimentacao: null}`) | 403, 404, 422 | RF-15, RN-17 |
| `GET /ingredientes/{id}/extrato?de=AAAA-MM-DD&ate=AAAA-MM-DD` | A, T | `{ingrediente, saldo_inicial_periodo, movimentacoes: [{id, tipo, quantidade, saldo_apos, criado_em, autor: {usuario_id?, pedido_numero?}, referencia?, motivo?}]}` | 403 (C), 404 | RF-18 |
| `PUT/PATCH/DELETE /movimentacoes/{id}` | — | não existe | 405 | RN-17 |

Tipos de movimentação: `entrada`, `ajuste`, `baixa_pedido`, `estorno_pedido`, `saldo_inicial`.

## 2. Ficha técnica, variações e adicionais

| Método e rota | Papéis | Corpo / retorno | Erros | Requisitos |
|---|---|---|---|---|
| `PUT /itens/{id}/ficha` | A | `[{ingrediente_id, quantidade>0}]` (lista vazia = sem ficha) | 403, 404, 422 | RF-13, RN-13 |
| `PUT /itens/{id}/variacao` | A | `{nome_grupo, opcoes: [{id?, nome, preco_centavos>0, ordem, disponivel, ficha: [...]}]}`; `null` remove o grupo | 403, 404, 422 | RF-19, RN-19 |
| `PUT /itens/{id}/adicionais` | A | `[{id?, nome, preco_centavos>=0, ordem, disponivel, ficha: [...]}]` | 403, 404, 422 | RF-19, RN-20 |
| `GET /itens` (R1) | A, T, C | ganha `ficha`, `variacao` e `adicionais` em cada item, e `sem_ficha: bool` | — | RF-13 |

Regras de validação comuns da ficha: ingrediente ativo e do mesmo restaurante, sem repetir, quantidade `int` > 0 (422 nos demais casos).

## 3. Pedido (extensões da R1)

- `GET /fila` e `GET /pedidos/{id}`: cada item ganha `variacao?` (nome da opção), `adicionais: [nome]` e `observacao?` (por item, RN-21).
- `GET /pedidos/{id}` (A, T) ganha `consumo: [{ingrediente, quantidade}]`, o que foi baixado na confirmação.
- `POST /pedidos/{id}/cancelar`: em `Recebido`, cria movimentações `estorno_pedido` com as quantidades de `consumo`; em `Em preparo`, não estorna (RN-16).

## 4. Robô (máquina de estados)

Novos estados, entre `ITENS` e `QUANTIDADE` e no carrinho:

```
ITENS → [VARIACAO] → [ADICIONAIS] → QUANTIDADE → CARRINHO
CARRINHO: 1 Adicionar mais itens · 2 Remover item · 3 Finalizar pedido · 4 Observação em um item · 0 Cancelar
CARRINHO --4--> OBS_ITEM_ESCOLHA → [OBS_ITEM_QTD] → OBS_ITEM_TEXTO → CARRINHO
```

- `VARIACAO`: só se o item tiver grupo; obrigatória (RN-19).
- `ADICIONAIS`: só se o item tiver adicionais; aceita "0" (nenhum) ou números separados por vírgula, sem repetir, até 5 (RN-20).
- `OBS_ITEM_QTD`: só se a linha tiver mais de uma unidade; aceita de 1 até a quantidade da linha. As unidades escolhidas viram uma linha nova com a observação; se já existir linha igual, as quantidades somam (RN-22).
- Na confirmação, a disponibilidade por estoque (RN-15) é conferida com os ingredientes travados; se uma linha não couber, o pedido não é criado e o cliente volta ao carrinho com aviso (BDD-BX-06).
- A chave da linha do carrinho passa a ser `(item_id, opcao_id, adicionais ordenados, observacao)` (RN-22).

## 5. Modelo de dados (acréscimos)

`ingrediente(id, restaurante_id, nome, unidade, saldo, estoque_minimo, bloqueia_venda, ativo)` · `movimentacao_estoque(id, restaurante_id, ingrediente_id, tipo, quantidade, saldo_apos, criado_em, usuario_id?, pedido_id?, referencia?, motivo?)` · `ficha_item(item_id, ingrediente_id, quantidade)` · `variacao_opcao(id, restaurante_id, item_id, nome, preco_centavos, ordem, disponivel)` · `ficha_opcao(opcao_id, ingrediente_id, quantidade)` · `adicional(id, restaurante_id, item_id, nome, preco_centavos, ordem, disponivel)` · `ficha_adicional(adicional_id, ingrediente_id, quantidade)` · `item.nome_grupo_variacao?` · `pedido_item` ganha `opcao_id?, opcao_nome?, adicionais_json, observacao?` · `consumo_pedido(pedido_id, ingrediente_id, quantidade)`

Únicos: `(restaurante_id, nome)` em ingrediente; `(item_id, ingrediente_id)` nas fichas. Índice `(restaurante_id, ingrediente_id, criado_em)` em movimentação. Migrações a partir da `0005`.
