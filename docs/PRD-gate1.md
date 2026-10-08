# PRD — PDV Restaurantes · Gate 1 (Definição)

- Objetivo: OBJ-PDV-001 · Modo: greenfield · Trilha: standard · Gate final: Gate 4 (somente R1)
- Especificador: PM-02 (escopo) + BA-02 (regras) · Revisor: QA-01 (sequencial, mesmo agente — não independente)
- Decisões de origem: DEC-01..DEC-03 e grill R2 (Q4 menu guiado, Q5 só registra pagamento, Q6 Docker Compose)
- Legenda: **[C]** confirmado pelo PM · **[H]** hipótese da squad, vale até o PM recusar no Gate 1

## 1. Dores de negócio (DN)

- **DN-01 (Pedido perdido):** pedidos por WhatsApp chegam como texto livre, são copiados à mão e se perdem ou saem errados. [H]
- **DN-02 (Fila da cozinha):** a cozinha não sabe a ordem nem o status dos pedidos; o atendente fica perguntando. [H]
- **DN-03 (Estoque cego):** o restaurante não sabe quanto ingrediente gastou nem quando vai faltar. [H]
- **DN-04 (Entrega sem controle):** não há registro de quem levou o pedido, quando saiu e se chegou. [H]
- **DN-05 (Caixa e números):** fechamento de caixa e faturamento são feitos em papel ou planilha. [H]
- **DN-06 (Custo de entrada):** pequenos restaurantes não pagam por integração oficial nem por sistemas caros. [C]

## 2. Objetivos (OBJ)

- **OBJ-01 (Pedido estruturado):** 100% dos pedidos do WhatsApp entram no sistema como itens estruturados, sem redigitação. → DN-01
- **OBJ-02 (Cozinha em tempo real):** a cozinha vê a fila ordenada e muda o status; o cliente é avisado no WhatsApp. → DN-02
- **OBJ-03 (Consumo automático):** cada pedido baixa ingredientes pela ficha técnica; alerta de estoque mínimo. → DN-03
- **OBJ-04 (Entrega rastreada):** cada entrega tem entregador, horários de saída/chegada e taxa por bairro. → DN-04
- **OBJ-05 (Caixa e relatórios):** abertura/fechamento de caixa, formas de pagamento e relatório diário. → DN-05
- **OBJ-06 (Custo zero no MVP):** MVP roda sem serviço pago além de uma VPS. → DN-06

## 3. Release train

| Fatia | Escopo | Objetivos | Até o gate |
|---|---|---|---|
| **R1** | Cadastro do restaurante, cardápio, robô de pedido no WhatsApp, fila da cozinha (KDS) | OBJ-01, OBJ-02, OBJ-06 | **Gate 4** |
| R2 | Ficha técnica, ingredientes, estoque, baixa automática, alertas | OBJ-03 | Gate 1 |
| R3 | Entregadores, taxa por bairro, rastreio de status de entrega | OBJ-04 | Gate 1 |
| R4 | Caixa, pagamentos (Pix integrado), relatórios, NFC-e | OBJ-05 | Gate 1 |

## 4. Escopo da R1

### Dentro
1. **Restaurantes (multi-tenant):** cadastro do restaurante, usuários (admin, atendente, cozinha), isolamento total de dados entre restaurantes. [C]
2. **Conexão WhatsApp:** o admin conecta o número lendo um QR code no painel; o painel mostra status (conectado/desconectado). [C]
3. **Cardápio:** categorias, itens, preço, descrição, disponível/indisponível, observação livre por item. [H]
4. **Robô de menu guiado:** saudação → categorias → itens → quantidade → carrinho → retirada ou entrega (endereço em texto) → forma de pagamento → confirmação. [C]
5. **Pedido:** número sequencial por restaurante por dia, itens, total, tipo, endereço, forma de pagamento, troco. [H]
6. **Fila da cozinha (KDS):** painel web com pedidos confirmados em ordem de chegada; status Recebido → Em preparo → Pronto → Finalizado. [H]
7. **Avisos ao cliente:** mensagem automática no WhatsApp a cada mudança de status. [H]
8. **Cancelamento:** atendente cancela com motivo; cliente é avisado. [H]
9. **Horário de funcionamento:** fora do horário, o robô informa o horário e não aceita pedido. [H]

### Fora (nesta fatia)
- Pagamento online, Pix integrado, NFC-e, caixa (R4) · Ficha técnica e estoque (R2) · Taxa de entrega, entregadores (R3)
- Robô com IA / texto livre (fatia futura) · App mobile nativo · Cardápio com fotos no WhatsApp [H]
- Pedido no balcão/mesa (PDV presencial) — fica para R4 [H]

## 5. Regras de negócio candidatas (BA-02)

| ID | Regra | Exemplo de limite |
|---|---|---|
| **RN-01 (Isolamento):** | Um usuário só lê e altera dados do próprio restaurante. | Atendente do restaurante A pede o pedido 10 do restaurante B → recusado (404/403) |
| **RN-02 (Dinheiro):** | Valores em centavos inteiros (BRL); total = soma de (preço × quantidade); sem arredondamento. | 3 × R$ 12,90 = 3870 centavos |
| **RN-03 (Preço congelado):** | O pedido guarda o preço do item no momento da confirmação. | Preço alterado depois não muda pedido já feito |
| **RN-04 (Item indisponível):** | Item indisponível não aparece no robô e não pode entrar no carrinho. | Item desativado com carrinho aberto → removido com aviso ao cliente |
| **RN-05 (Quantidade):** | Quantidade inteira de 1 a 20 por item. [H] | "0", "21", "abc" → robô pede de novo |
| **RN-06 (Sessão do robô):** | Carrinho expira após 30 min sem resposta. [H] | Resposta após 31 min → reinicia do menu |
| **RN-07 (Horário):** | Pedido só é confirmado dentro do horário de funcionamento. | 23:01 com fechamento às 23:00 → recusado |
| **RN-08 (Troco):** | Pagamento em dinheiro pergunta troco; valor do troco ≥ total. | Total R$ 38,70, troco para R$ 30 → recusado |
| **RN-09 (Transição de status):** | Status só avança na ordem; "Cancelado" possível antes de "Pronto". | Pronto → Em preparo → recusado |
| **RN-10 (LGPD mínima):** | Coleta só telefone, nome do perfil e endereço quando for entrega; finalidade exclusiva do pedido; endereço/telefone não vão para logs. | Log de erro com telefone completo → violação |

## 6. Solução candidata (vira ADR no Gate 2)

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| `api` | Python · FastAPI · SQLAlchemy · PostgreSQL | Domínio, regras, multi-tenant, máquina de estados do robô e do pedido |
| `wa-gateway` | TypeScript · Node · Baileys (não oficial) | Só transporte: recebe/envia mensagens, sessão por restaurante, QR code. Sem regra de negócio (RSK-01/02) |
| `web` | React · TypeScript | Painel admin (cardápio, conexão WhatsApp) e KDS da cozinha |
| Infra | Docker Compose | Local e VPS |

Contrato entre `wa-gateway` e `api`: webhook HTTP de mensagem recebida + endpoint de envio. O domínio só conhece a porta `CanalMensagens`, para trocar pela API oficial depois.

## 7. Critérios de sucesso da R1 (Gate 4)

1. Um cliente faz um pedido completo pelo robô sem intervenção humana e ele aparece no KDS em até 5 s. [H]
2. Mudança de status no KDS gera aviso no WhatsApp do cliente.
3. Testes de isolamento entre restaurantes passam (cenários negativos de RN-01).
4. Verificador de RTM sem cenário negativo órfão; sensor de mutação ≥ 85% nos módulos de regra de negócio.

## 8. Pendências para o Gate 2

- Confirmar hipóteses [H] marcadas acima (o PM pode recusar qualquer uma ao aprovar).
- Robô em dois níveis (categorias → itens) ou lista única; cardápio com adicionais/variações (ex.: tamanho) — proposta: sem variações na R1.
