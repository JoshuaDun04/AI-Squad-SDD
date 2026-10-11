# Plano do piloto em campo — R1

- Objetivo: validar no uso real as dores DN-01 (pedido perdido ou errado) e DN-02 (cozinha sem fila), com custo de entrada mínimo (DN-06)
- Pré-requisito: R1 implantada pelo [roteiro da VPS](implantacao-vps.md), com `./deploy/pdv.sh verificar` terminando em `Tudo certo.`
- Fases: **0 — ensaio interno** (1 a 2 dias, sem cliente real) → **1 — piloto assistido** (2 semanas, 1 restaurante) → **decisão** (seguir, ajustar ou parar)

## Fase 0 — Ensaio interno

Você faz o papel do restaurante e do cliente, com dois celulares: o do restaurante (número dedicado, conectado pelo QR) e um segundo número no papel de cliente. Cada linha repete no WhatsApp real um cenário que hoje só foi testado com o gateway simulado.

| # | Teste | Cenário | Como fazer | Esperado |
|---|---|---|---|---|
| 1 | Conectar o número | BDD-WA-01 | Painel → WhatsApp → Gerar QR code; ler no celular | Status "Conectado" em até 30 s |
| 2 | Pedido de retirada com Pix | BDD-ROB-01, BDD-PED-01 | Do celular cliente: "oi" → categoria → item → quantidade → finalizar → retirada → Pix → confirmar | Resumo correto; "Pedido #1 recebido"; ticket na cozinha em até 5 s |
| 3 | Entrega com dinheiro e troco | BDD-PED-02 | Entrega, endereço completo, dinheiro, troco para 50 | Atendente vê endereço e troco no detalhe; cozinha não vê endereço |
| 4 | Observação no pedido | BDD-OBS-01 | No resumo, "Adicionar observação": "sem cebola" | Observação em destaque no ticket |
| 5 | Avisos de status | BDD-COZ-01, BDD-COZ-02 | Cozinha: Começar preparo → Marcar pronto; atendente: Entregue | Cliente recebe uma mensagem a cada passo |
| 6 | Cancelamento | BDD-CAN-01 | Atendente cancela com motivo | Cliente recebe o motivo; pedido sai da fila |
| 7 | Item que acaba no meio da conversa | BDD-CAR-04 | Cliente com item no carrinho; admin marca indisponível; cliente segue | Aviso e item removido |
| 8 | Fora do horário | BDD-HOR-02 | Ajuste o horário para fechar daqui a 2 min e mande "oi" depois | Robô informa quando abre; não mostra menu |
| 9 | Carrinho abandonado | BDD-ROB-06 | Monte um carrinho, espere 31 min, mande "3" | Aviso de carrinho expirado e menu do início |
| 10 | Entradas inválidas | BDD-ROB-04, BDD-ROB-05 | Envie "dois", "0", "21", figurinha, áudio | Robô pede de novo, sem travar |
| 11 | Dois clientes ao mesmo tempo | ISO e REV-01 | Dois celulares cliente pedindo juntos | Pedidos separados, numeração sem repetir |
| 12 | Reinício do servidor | ADR-0002, contatos LID | `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart wa-gateway api` no meio de um pedido aberto | Sessão continua conectada; o pedido segue; avisos chegam |
| 13 | Desconectar e reconectar | BDD-WA-02 | No celular, encerre o aparelho conectado | Verificação acusa; novo QR reconecta |
| 14 | Backup e restauração | — | `./deploy/pdv.sh backup`; restaure num ensaio | Dados e sessão de volta |
| 15 | Logs sem dados pessoais | BDD-LGPD-02 | Depois dos testes, `./deploy/pdv.sh verificar` | "logs sem telefone completo" |

Anote cada teste como **ok**, **falhou** ou **estranho**, com hora e um print se ajudar. Qualquer **falhou** nos testes 2, 5, 11, 12 ou 15 bloqueia a Fase 1.

## Fase 1 — Piloto assistido

### Antes do primeiro dia

- [ ] Restaurante escolhido: pequeno, já recebe pedidos pelo WhatsApp, dono disposto a dar retorno diário
- [ ] Número dedicado do restaurante conectado (ou migração do número atual, ciente do risco RSK-01)
- [ ] Cardápio completo com preços conferidos pelo dono
- [ ] Horários reais de funcionamento
- [ ] Tela da cozinha: tablet, notebook ou TV com navegador, logada com o usuário "cozinha"
- [ ] Atendente treinado em: detalhe do pedido, cancelamento com motivo, "Entregue"
- [ ] Mensagem para os clientes avisando que os pedidos passam a ser por menu numerado
- [ ] Clientes informados de que o telefone e o endereço servem só para o pedido (RN-10, LGPD)
- [ ] Alerta do ntfy chegando no seu celular e no do dono
- [ ] Plano B combinado: se o robô parar, o restaurante volta a anotar à mão e avisa você

### Durante (todo dia, 10 minutos)

1. `./deploy/pdv.sh relatorio 1` e preencher o registro diário abaixo
2. Perguntar ao dono: algum pedido chegou fora do robô? Algum saiu errado? Alguma reclamação?
3. Conferir o painel de pedidos do dia contra o que a cozinha produziu

### Métricas e critérios de sucesso

Os alvos são hipóteses da squad para o PM confirmar antes do início.

| Métrica | Fonte | Alvo |
|---|---|---|
| Pedidos de WhatsApp que entraram pelo robô | relatório (pedidos) ÷ (pedidos + pedidos fora do robô, anotados pelo dono) | ≥ 80% na segunda semana |
| Pedidos perdidos (feitos pelo cliente e não produzidos) | conversa com o dono | 0 |
| Pedidos com erro de item, quantidade ou valor | conversa com o dono | ≤ 2% |
| Tempo da confirmação até "Em preparo" | relatório (mediana) | ≤ 5 min |
| Cancelamentos por falha do sistema | relatório (motivos) | 0 |
| Horas com o WhatsApp desconectado em horário de funcionamento | alertas do ntfy | ≤ 1 h na semana |
| Telefone completo em log | verificação | nunca |

### Registro diário

| Dia | Pedidos (relatório) | Fora do robô | Erros | Cancelados (motivo) | Mediana até preparo | Desconexões | Observações do dono |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

### Quando parar o piloto

- Número do restaurante bloqueado pelo WhatsApp (RSK-01): parar, voltar ao manual e reavaliar a API oficial (troca de adaptador, ADR-0002)
- Pedido perdido por falha do sistema duas vezes na mesma semana
- Qualquer vazamento de dado pessoal

## Decisão ao fim das duas semanas

Leve à squad: o registro diário, `./deploy/pdv.sh relatorio 14` e os comentários do dono. A decisão é uma de três:
- **Seguir:** ampliar para mais restaurantes e abrir o Gate 3 da R2.
- **Ajustar:** corrigir o que o piloto mostrou e repetir uma semana.
- **Parar:** registrar o motivo como DEC.
