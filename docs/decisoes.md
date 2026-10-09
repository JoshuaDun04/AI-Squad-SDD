# Registro de decisões (DEC)

DEC-01..DEC-06 foram tomadas antes deste repositório existir e estão citadas no PRD e na RTM. Novas decisões entram aqui.

## DEC-07 — Observação livre: por pedido na R1, por item na R2

- Data: 08/10/2026 · Decisor: PM (delegou a recomendação à squad) · Origem: PRD §4 item 3 [H], pendente desde o Gate 2

**Decisão.** A R1 aceita uma observação livre **por pedido**, opcional, de até 140 caracteres. O cliente adiciona pela opção "3 - Adicionar observação" no resumo, antes de confirmar. A observação aparece em destaque no ticket da cozinha e no detalhe do pedido. A observação **por item** fica para a R2, junto com adicionais e variações, porque depende da ficha técnica.

**Por quê.**
- Pedido saindo errado é a dor DN-01. "Sem cebola" e "bem passado" são o caso mais comum que hoje se perde no texto livre do WhatsApp.
- Como opção no resumo, quem não precisa não ganha nenhuma mensagem a mais.
- Observação por item obrigaria a separar linhas iguais com observações diferentes, o que quebra a regra de somar quantidades (BDD-ROB-03), e se sobrepõe às variações da R2.

**Consequências.** Nova regra RN-11, cenários BDD-OBS-01..03, coluna `pedido.observacao` (migração 0002) e campo `observacao` em `GET /fila` e `GET /pedidos/{id}`. A observação nunca vai para log, porque o cliente pode escrever dado de saúde (ex.: alergia).

## DEC-08 — Variações e adicionais entram na R2, junto com o estoque

- Data: 08/10/2026 · Decisor: PM (delegou a recomendação à squad) · Origem: DEC-07, PRD §8 ("sem variações na R1")

**Decisão.** A R2 inclui, além de estoque e ficha técnica, um grupo de variação obrigatório por item (ex.: tamanho), adicionais opcionais e observação por item.

**Por quê.** A ficha técnica precisa saber o que foi vendido de fato: um suco de 500 ml gasta mais polpa que um de 300 ml, e um adicional de queijo baixa queijo. Fazer o estoque antes das variações obrigaria a refazer a ficha da linha do pedido logo em seguida. A observação por item foi adiada da R1 para cá pela DEC-07.

**Consequências.** Escopo maior que o PRD original para a R2 (OBJ-07, RN-19..RN-22, RF-19, RF-20). Fica de fora a variação com mais de um grupo por item. O PM pode recusar ao aprovar o Gate 2 da R2 (pergunta 3 da RTM-r2); nesse caso, as variações viram uma fatia própria logo depois.
