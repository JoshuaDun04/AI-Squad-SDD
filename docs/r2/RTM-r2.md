# RTM — PDV Restaurantes · Fatia R2 (Estoque, ficha técnica e cardápio com variações)

- Objetivo: OBJ-PDV-002 · **Gate 2 (Especificação)** · Fonte: PRD-gate1.md §3 (R2), [DEC-07](../decisoes.md), [DEC-08](../decisoes.md), ADR-0001..0010
- Estado das evidências: **não executadas** (a implementação começa no Gate 3)
- Cenários: [bdd-r2.md](bdd-r2.md) · Contratos: [api-contract-r2.md](api-contract-r2.md) · Glossário: [CONTEXT.md](../../CONTEXT.md)
- Legenda: **[C]** confirmado (PRD aprovado ou decisão registrada) · **[H]** hipótese da squad; vale até o PM recusar ao aprovar este Gate 2
- Continua valendo tudo da R1 (RN-01..RN-11, RF-01..RF-11, RT-01..RT-08)

## Dores de negócio

- **DN-03 (Estoque cego):** o restaurante não sabe quanto ingrediente gastou nem quando vai faltar. [C]
- **DN-01 (Pedido perdido), complemento:** pedidos com tamanho, adicional ou "sem cebola" num item específico ainda chegam como texto e saem errados. [H]

## Objetivos

- **OBJ-03 (Consumo automático):** cada pedido baixa ingredientes pela ficha técnica; alerta de estoque mínimo. [C]
- **OBJ-07 (Pedido completo no robô):** o cliente escolhe tamanho, adicionais e observação de cada item sem texto livre; a cozinha recebe a linha exata. [H, DEC-08]

## Requisitos de negócio

- **RN-12 (Unidade base inteira):** todo ingrediente tem uma unidade base — grama (`g`), mililitro (`ml`) ou unidade (`un`) — e todo saldo e quantidade é um inteiro nessa unidade. Não há fração. [H]
- **RN-13 (Ficha técnica):** um item pode ter ficha técnica: lista de ingredientes com quantidade inteira maior que zero na unidade base. Item sem ficha é vendido normalmente e não baixa estoque; o painel sinaliza "sem ficha". [H]
- **RN-14 (Baixa automática):** ao criar o pedido, o estoque baixa a ficha × quantidade de cada linha, somando a ficha da variação e dos adicionais escolhidos. A baixa acontece junto com a criação do pedido: ou os dois acontecem, ou nenhum. [C]
- **RN-15 (Saldo negativo permitido):** a venda não é bloqueada por falta de saldo, porque a contagem de um restaurante pequeno nem sempre é exata; o saldo pode ficar negativo e o painel destaca. A exceção é o ingrediente marcado "bloqueia venda": quando o saldo não cobre uma porção, os itens, opções e adicionais que o usam ficam indisponíveis no robô (mesmo efeito da RN-04). A regra é conferida de novo na confirmação, com os saldos travados; se não couber mais, o pedido não é criado e a linha sai do carrinho com aviso. [H]
- **RN-16 (Estorno no cancelamento):** pedido cancelado em "Recebido" devolve ao estoque exatamente o que baixou. Cancelado em "Em preparo" não devolve, porque o ingrediente já foi usado. [H]
- **RN-17 (Movimentação auditável):** o saldo só muda por movimentação registrada — saldo inicial, entrada, ajuste de inventário, baixa de pedido ou estorno — com tipo, quantidade com sinal, saldo resultante, data, autor (usuário ou pedido) e motivo quando for ajuste. Movimentações não são editadas nem apagadas; erro se corrige com novo ajuste. [H]
- **RN-18 (Alerta de mínimo):** ingrediente com saldo menor ou igual ao estoque mínimo aparece em alerta no painel, ordenado do mais crítico (maior déficit proporcional) ao menos crítico. [C]
- **RN-19 (Variação):** um item pode ter um grupo de variação obrigatório (ex.: Tamanho: P, M, G). Cada opção tem preço próprio, que substitui o preço do item, e ficha técnica própria, que substitui a do item. Se nenhuma opção estiver disponível, o item some do robô. [H, DEC-08]
- **RN-20 (Adicionais):** um item pode ter adicionais opcionais (ex.: queijo extra), até 5 por linha, sem repetir. O preço de cada adicional é somado ao preço unitário e a ficha é somada à ficha da linha. [H, DEC-08]
- **RN-21 (Observação por item):** cada linha do pedido aceita uma observação livre de até 80 caracteres, que aparece no ticket da cozinha e não vai para log. Numa linha com mais de uma unidade, o cliente diz quantas unidades levam a observação; essas unidades viram uma linha separada. A observação do pedido (RN-11) continua existindo. [H, DEC-07]
- **RN-22 (Linha do pedido):** duas escolhas só somam quantidade (RN-05) quando item, variação, adicionais e observação são iguais; senão viram linhas separadas. Preço unitário, nomes e ficha da linha são congelados na confirmação (extensão da RN-03). [H]
- **RN-23 (Papéis no estoque):** admin cadastra ingredientes, fichas, variações e adicionais e faz ajustes de inventário; admin e atendente lançam entradas de mercadoria; cozinha consulta saldos e alertas sem alterar. [H]

## Requisitos funcionais

- **RF-12 (Ingredientes):** admin cria, edita e desativa ingredientes (nome, unidade base, estoque mínimo, bloqueia venda). Ingrediente desativado sai das listas, mas o histórico continua.
- **RF-13 (Ficha técnica):** admin define a ficha do item, de cada opção de variação e de cada adicional.
- **RF-14 (Entrada de mercadoria):** admin ou atendente registra entrada de um ou mais ingredientes, com quantidade positiva e referência opcional (ex.: número da nota).
- **RF-15 (Inventário):** admin informa a contagem real de um ingrediente; o sistema registra um ajuste com a diferença e o motivo obrigatório.
- **RF-16 (Baixa e estorno):** a confirmação do pedido baixa o estoque (RN-14); o cancelamento em "Recebido" estorna (RN-16).
- **RF-17 (Painel de estoque e alertas):** lista de ingredientes com saldo, mínimo e situação (ok, abaixo do mínimo, negativo); contador de alertas visível em todas as páginas do painel.
- **RF-18 (Extrato):** extrato de movimentações de um ingrediente por período, com saldo após cada movimentação.
- **RF-19 (Variações e adicionais no cardápio e no robô):** admin cadastra grupos de variação e adicionais por item; o robô pergunta a variação (se houver) e oferece os adicionais (se houver) antes da quantidade, e o resumo, o ticket e o detalhe mostram a linha completa.
- **RF-20 (Observação por item no robô):** o carrinho oferece "Adicionar observação a um item": o cliente escolhe a linha, a quantidade de unidades (se a linha tiver mais de uma) e o texto; a observação aparece na linha do carrinho, do resumo, do ticket e do detalhe.

## Requisitos técnicos

- **RT-09 (Razão de estoque):** tabela `movimentacao_estoque` só com inserção; saldo materializado em `ingrediente.saldo`, atualizado na mesma transação da movimentação (ADR-0007).
- **RT-10 (Baixa atômica e sem deadlock):** a baixa trava as linhas dos ingredientes com `SELECT ... FOR UPDATE` em ordem crescente de id, dentro da mesma transação que cria o pedido e trava a conversa (ADR-0006, ADR-0007).
- **RT-11 (Inteiros na unidade base):** quantidades `int` em toda a API e no banco; o painel converte kg/L para g/ml na borda (ADR-0008).
- **RT-12 (Disponibilidade por estoque):** a montagem do cardápio do robô considera o saldo dos ingredientes "bloqueia venda" na mesma leitura que já filtra itens indisponíveis; sem job agendado (ADR-0009).
- **RT-13 (Linha de pedido completa):** `pedido_item` passa a guardar variação, adicionais, observação e a ficha consumida, todos congelados (ADR-0010). Migrações Alembic a partir da 0005, compatíveis com pedidos da R1.

## Matriz de rastreabilidade

| ID Dor | ID Objetivo | ID Requisito Negócio | ID Requisito Funcional | ID Requisito Técnico | Cobertura BDD (Tríade) | Gate & Evidência de Verificação |
|---|---|---|---|---|---|---|
| DN-03 | OBJ-03 | RN-12, RN-23, RN-01 | RF-12 | RT-11, RT-01 | BDD-ING-01 @principal; BDD-ING-02 @variacao; BDD-ING-03, BDD-ING-04 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-13, RN-12 | RF-13 | RT-11 | BDD-FT-01 @principal; BDD-FT-02 @variacao; BDD-FT-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-17, RN-23 | RF-14 | RT-09 | BDD-ENT-01 @principal; BDD-ENT-02 @variacao; BDD-ENT-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-17, RN-23 | RF-15 | RT-09 | BDD-INV-01 @principal; BDD-INV-02 @variacao; BDD-INV-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-14, RN-15, RN-17 | RF-16 | RT-09, RT-10, RT-12 | BDD-BX-01 @principal; BDD-BX-02, BDD-BX-03 @variacao; BDD-BX-04, BDD-BX-05, BDD-BX-06 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-16, RN-17 | RF-16 | RT-09 | BDD-EST-01 @principal; BDD-EST-02 @variacao; BDD-EST-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-18, RN-23 | RF-17 | RT-12 | BDD-ALR-01 @principal; BDD-ALR-02 @variacao; BDD-ALR-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-17 | RF-18 | RT-09 | BDD-EXT-01 @principal; BDD-EXT-02 @variacao; BDD-EXT-03 @negative | Gate 3 (pendente) |
| DN-01 | OBJ-07 | RN-19, RN-20, RN-22 | RF-19 | RT-13 | BDD-VAR-01 @principal; BDD-VAR-02 @variacao; BDD-VAR-03, BDD-VAR-04 @negative | Gate 3 (pendente) |
| DN-01 | OBJ-07 | RN-21, RN-22, RN-10 | RF-20 | RT-13 | BDD-OBI-01 @principal; BDD-OBI-02 @variacao; BDD-OBI-03 @negative | Gate 3 (pendente) |
| DN-03 | OBJ-03 | RN-01 | RF-12..RF-18 | RT-01 | BDD-ISO-04, BDD-ISO-05 @negative | Gate 3 (pendente) |

## Fora da R2

- Custo de ingrediente, CMV e margem (dependem de caixa e relatórios, R4).
- Fornecedores, pedido de compra e validade/lote de ingredientes.
- Conversão automática entre unidades diferentes de um mesmo ingrediente (ex.: "caixa com 12").
- Alerta de estoque mínimo por WhatsApp para o dono (só no painel na R2). [H]
- Variação com mais de um grupo por item (ex.: tamanho **e** massa). [H]

## Perguntas para o PM aprovar este Gate 2

1. **Venda com saldo negativo (RN-15):** a squad propõe não bloquear, com bloqueio só para ingredientes marcados. Aceita?
2. **Estorno só em "Recebido" (RN-16):** cancelado em "Em preparo" não devolve. Aceita?
3. **Escopo de variações e adicionais na R2 (DEC-08):** amplia a R2 além do PRD original (que tinha só estoque). A alternativa é uma fatia própria depois da R2, com o custo de refazer a ficha técnica da linha depois.
4. **Entrada de mercadoria pelo atendente (RN-23):** ou só o admin?
5. **Até onde vai a R2:** o PRD previa a R2 só até o Gate 1. A squad propõe levá-la até o Gate 4 (implementação e validação), como a R1.
