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
