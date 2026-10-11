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

- Data: 08/10/2026 · Decisor: PM (delegou a recomendação à squad; **confirmada pelo PM em 10/10/2026**, DEC-09) · Origem: DEC-07, PRD §8 ("sem variações na R1")

**Decisão.** A R2 inclui, além de estoque e ficha técnica, um grupo de variação obrigatório por item (ex.: tamanho), adicionais opcionais e observação por item.

**Por quê.** A ficha técnica precisa saber o que foi vendido de fato: um suco de 500 ml gasta mais polpa que um de 300 ml, e um adicional de queijo baixa queijo. Fazer o estoque antes das variações obrigaria a refazer a ficha da linha do pedido logo em seguida. A observação por item foi adiada da R1 para cá pela DEC-07.

**Consequências.** Escopo maior que o PRD original para a R2 (OBJ-07, RN-19..RN-22, RF-19, RF-20). Fica de fora a variação com mais de um grupo por item. O PM pode recusar ao aprovar o Gate 2 da R2 (pergunta 3 da RTM-r2); nesse caso, as variações viram uma fatia própria logo depois.

## DEC-09 — Aprovação do Gate 2 da R2

- Data: 10/10/2026 · Decisor: PM · Origem: perguntas 1 a 5 da RTM-r2

**Decisões.**
1. **Venda com saldo negativo (RN-15):** aceita como proposta. A venda não é bloqueada por saldo; só os ingredientes marcados "bloqueia venda" tiram itens do robô.
2. **Estorno (RN-16):** aceito. O cancelamento devolve ao estoque só se o pedido ainda não entrou em preparo (status "Recebido").
3. **Variações, adicionais e observação por item na R2 (DEC-08):** aceito.
4. **Entrada de mercadoria (RN-23): só o admin.** A proposta da squad (admin e atendente) foi recusada. O atendente consulta saldos, alertas e extrato, sem alterar.
5. **Até onde vai a R2:** segue o previsto no release train do PRD (§3). A R2 foi além do Gate 1, a pedido do PM, e encerra com este Gate 2 aprovado. Gate 3 (implementação) e Gate 4 (validação) da R2 abrem só quando o PM iniciar um novo objetivo para ela.

**Consequências.** Todas as hipóteses [H] da RTM-r2 viram [C]. RN-23, RF-14, BDD-ENT-01, BDD-ENT-03 e o contrato de `POST /estoque/entradas` passam a aceitar só o admin. ADR-0007..0010 passam de "proposed" para "accepted". Com a R1 no Gate 4 e R2 a R4 especificadas, o release train do OBJ-PDV-001 está cumprido; o que resta da R1 é operacional (build e WhatsApp real na VPS).
