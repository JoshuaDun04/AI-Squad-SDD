# RTM — PDV Restaurantes · Fatia R1

- Objetivo: OBJ-PDV-001 · Fonte: PRD-gate1.md (aprovado no Gate 1), DEC-01..07 ([decisoes.md](decisoes.md)), ADR-0001..0006
- Estado das evidências: **executadas em 08/10/2026 sobre código novo, após revisão independente** (o projeto foi reconstruído do zero; a evidência anterior a esta data não tinha código correspondente e foi descartada). Detalhes em [parecer-gate4.md](parecer-gate4.md).
- Cenários: [bdd-r1.md](bdd-r1.md) · Contratos: [api-contract-r1.md](api-contract-r1.md) · Glossário: [CONTEXT.md](../CONTEXT.md)
- Verificação automática: `python pdv/api/scripts/verificar_rtm.py` (cobertura BDD + regras da ADR-0001)

## Dores de negócio

- **DN-01 (Pedido perdido):** pedidos por WhatsApp chegam em texto livre, são redigitados e se perdem ou saem errados.
- **DN-02 (Fila da cozinha):** a cozinha não sabe a ordem nem o status dos pedidos.
- **DN-06 (Custo de entrada):** restaurantes pequenos não pagam integração oficial nem sistemas caros.

## Objetivos

- **OBJ-01 (Pedido estruturado):** todo pedido do WhatsApp entra como itens estruturados, sem redigitação.
- **OBJ-02 (Cozinha em tempo real):** cozinha vê a fila ordenada, muda status e o cliente é avisado.
- **OBJ-06 (Custo zero no MVP):** a R1 roda sem serviço pago além de uma VPS.

## Requisitos de negócio

- **RN-01 (Isolamento):** usuário só lê e altera dados do próprio restaurante; recurso de outro restaurante responde 404.
- **RN-02 (Dinheiro):** valores em centavos inteiros; total = soma de preço × quantidade, sem arredondamento.
- **RN-03 (Preço congelado):** o pedido guarda o preço unitário do item no momento da confirmação.
- **RN-04 (Item indisponível):** item indisponível não aparece no robô nem entra no carrinho; se ficar indisponível com carrinho aberto, sai do carrinho com aviso.
- **RN-05 (Quantidade):** quantidade inteira de 1 a 20 por item.
- **RN-06 (Expiração da conversa):** carrinho expira após 30 min sem resposta do cliente; a próxima mensagem reinicia no menu.
- **RN-07 (Horário):** pedido só é confirmado dentro do horário de funcionamento do restaurante.
- **RN-08 (Troco):** pagamento em dinheiro pergunta troco; "sem troco" ou valor maior ou igual ao total.
- **RN-09 (Transição de status):** Recebido → Em preparo → Pronto → Finalizado, sem pular nem voltar; Cancelado só a partir de Recebido ou Em preparo.
- **RN-10 (LGPD mínima):** coleta só telefone, nome do perfil e endereço (quando entrega), para a finalidade do pedido; telefone e endereço não aparecem em logs.
- **RN-11 (Observação do pedido):** observação livre opcional por pedido, até 140 caracteres, adicionada no resumo antes de confirmar; aparece no ticket da cozinha e não vai para logs (DEC-07).

## Requisitos funcionais

- **RF-01 (Cadastro de restaurante):** criar restaurante com usuário admin (e-mail e senha).
- **RF-02 (Login e papéis):** login por e-mail e senha; papéis admin, atendente e cozinha com permissões distintas.
- **RF-03 (Gestão de usuários):** admin cria e desativa usuários do próprio restaurante.
- **RF-04 (Cardápio):** admin cria, edita, ordena e desativa categorias e itens (nome, descrição, preço, disponível).
- **RF-05 (Horário de funcionamento):** admin define horário por dia da semana (abertura e fechamento, fuso America/Manaus por padrão).
- **RF-06 (Conexão WhatsApp):** admin inicia conexão, vê o QR code e o status (desconectado, aguardando QR, conectado).
- **RF-07 (Robô: navegação e carrinho):** menu guiado por números: categorias → itens → quantidade → carrinho (adicionar mais, remover, finalizar, cancelar).
- **RF-08 (Robô: fechamento):** tipo (retirada/entrega), endereço em texto se entrega, forma de pagamento (Pix, dinheiro, cartão na entrega), troco, resumo, observação opcional (RN-11) e confirmação criam o pedido.
- **RF-09 (Fila da cozinha):** painel lista pedidos Recebido, Em preparo e Pronto em ordem de confirmação, atualizado em até 5 s.
- **RF-10 (Status e aviso):** cozinha/atendente avançam o status; cada mudança envia mensagem ao cliente.
- **RF-11 (Cancelamento):** atendente/admin cancela com motivo obrigatório; cliente é avisado.

## Requisitos técnicos

- **RT-01 (API multi-restaurante):** FastAPI + SQLAlchemy + PostgreSQL; repositórios recebem `restaurante_id` obrigatório (ADR-0001).
- **RT-02 (Autenticação):** senha com hash Argon2; JWT de acesso com expiração de 8 h contendo `usuario_id`, `restaurante_id` e `papel`.
- **RT-03 (Canal de mensagens):** porta `CanalMensagens`; gateway TS Baileys com `X-Gateway-Token`; deduplicação por `mensagem_id` (ADR-0002).
- **RT-04 (Máquina de estados do robô):** estado e carrinho persistidos por conversa; expiração avaliada na chegada da mensagem (ADR-0003).
- **RT-05 (Atualização da fila):** painel consulta a fila a cada 3 s (polling); critério de até 5 s.
- **RT-06 (Logs sem dados pessoais):** telefone mascarado (`*****-1234`) e endereço omitido em todo log.
- **RT-07 (Execução):** Docker Compose com `api`, `wa-gateway`, `web`, `db`; sobe com um comando.
- **RT-14 (Horários de status):** o pedido guarda a hora de cada mudança de status, para o relatório do piloto (DEC-10, migração 0005).
- **RT-08 (Número do pedido):** sequencial por restaurante por dia (fuso do restaurante), reinicia em 1 à meia-noite.

## Matriz de rastreabilidade

Arquivos de teste em `pdv/api/tests/`; cada teste leva `@pytest.mark.bdd("<ID>")`.

| ID Dor | ID Objetivo | ID Requisito Negócio | ID Requisito Funcional | ID Requisito Técnico | Cobertura BDD (Tríade) | Evidência de verificação (08/10/2026) |
|---|---|---|---|---|---|---|
| DN-06 | OBJ-06 | RN-01 | RF-01, RF-02, RF-03 | RT-01, RT-02 | BDD-AUT-01 @principal; BDD-AUT-02 @variacao; BDD-AUT-03, BDD-ISO-01, BDD-ISO-02, BDD-ISO-03 @negative | ✅ test_auth.py, test_isolamento.py, test_isolamento_repos.py, test_config.py |
| DN-01 | OBJ-01 | RN-01, RN-02, RN-04 | RF-04 | RT-01 | BDD-CAR-01 @principal; BDD-CAR-02 @variacao; BDD-CAR-03, BDD-CAR-04 @negative | ✅ test_cardapio.py, test_dominio.py |
| DN-01 | OBJ-01 | RN-07 | RF-05 | RT-01 | BDD-HOR-01 @principal; BDD-HOR-02 @variacao; BDD-HOR-03 @negative | ✅ test_horario.py, test_dominio.py |
| DN-06 | OBJ-06 | RN-01 | RF-06 | RT-03 | BDD-WA-01 @principal; BDD-WA-02 @variacao; BDD-WA-03, BDD-WA-04 @negative | ✅ test_canal.py; gateway: test/gateway.test.ts |
| DN-01 | OBJ-01 | RN-04, RN-05, RN-06 | RF-07 | RT-03, RT-04 | BDD-ROB-01 @principal; BDD-ROB-02, BDD-ROB-03 @variacao; BDD-ROB-04, BDD-ROB-05, BDD-ROB-06, BDD-ROB-07 @negative | ✅ test_robo.py, test_robo_textos.py, test_dominio.py, test_concorrencia.py |
| DN-01 | OBJ-01 | RN-02, RN-03, RN-07, RN-08, RN-10 | RF-08 | RT-04, RT-06, RT-08 | BDD-PED-01 @principal; BDD-PED-02, BDD-PED-03 @variacao; BDD-PED-04, BDD-PED-05, BDD-PED-06, BDD-PED-07 @negative | ✅ test_pedido.py, test_lgpd_logs.py, test_concorrencia.py |
| DN-02 | OBJ-02 | RN-01, RN-09 | RF-09, RF-10 | RT-05 | BDD-COZ-01 @principal; BDD-COZ-02 @variacao; BDD-COZ-03, BDD-COZ-04 @negative | ✅ test_cozinha.py; e2e Playwright (fila em < 5 s) |
| DN-02 | OBJ-02 | RN-09 | RF-11 | RT-03 | BDD-CAN-01 @principal; BDD-CAN-02 @variacao; BDD-CAN-03 @negative | ✅ test_cozinha.py; e2e Playwright |
| DN-01 | OBJ-01 | RN-10 | RF-08 | RT-06 | BDD-LGPD-01 @principal; BDD-LGPD-02 @negative | ✅ test_lgpd_logs.py; varredura dos logs reais do e2e |
| DN-01 | OBJ-01, OBJ-02 | RN-11, RN-10 | RF-08, RF-09 | RT-04 | BDD-OBS-01 @principal; BDD-OBS-02 @variacao; BDD-OBS-03 @negative | ✅ test_observacao.py, test_robo_textos.py |
| DN-06 | OBJ-06 | — | — | RT-07 | — (infra) | ✅ CI run #1 (11/10/2026): build das 3 imagens e e2e Playwright contra o compose |
| DN-02 | OBJ-02 | RN-09 | RF-10, RF-11 | RT-14 | — (técnico; teste sem cenário BDD) | ✅ test_cozinha.py (horários de cada status e do cancelamento); relatório do piloto testado em PostgreSQL |

## Fora da R1 (rastreados para R2–R4)

- **DN-03, DN-04, DN-05** e **OBJ-03, OBJ-04, OBJ-05** permanecem no PRD-gate1.md; entram nesta RTM quando sua fatia abrir o Gate 2.
- **Observação por item** vai para a R2, junto com adicionais e variações ([DEC-07](decisoes.md)). A R1 tem observação por pedido (RN-11).
