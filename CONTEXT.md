# PDV Restaurantes

Plataforma multi-restaurante que recebe pedidos pelo WhatsApp, organiza a produção na cozinha e, nas próximas fatias, controla estoque, entrega e caixa.

## Language

### Organização

**Restaurante**:
O cliente pagante da plataforma; unidade de isolamento de todos os dados.
_Avoid_: Tenant (só no código), loja, empresa

**Usuário**:
Pessoa da equipe do restaurante que acessa o painel, com um papel: admin, atendente ou cozinha.
_Avoid_: Operador, funcionário

**Cliente**:
Pessoa que faz pedidos pelo WhatsApp, identificada pelo número de telefone dentro de um restaurante.
_Avoid_: Consumidor, comprador, usuário

### Cardápio

**Categoria**:
Agrupamento de itens exibido como primeiro nível do menu do robô.

**Item**:
Produto vendável do cardápio, com preço em centavos e flag de disponibilidade.
_Avoid_: Produto, prato

### Pedido

**Conversa**:
Sessão do robô com um cliente, com estado atual do menu e carrinho; expira após 30 min sem resposta.
_Avoid_: Chat, sessão do WhatsApp

**Carrinho**:
Itens escolhidos numa conversa ainda não confirmada.

**Pedido**:
Carrinho confirmado pelo cliente, com preços congelados, número diário e status.
_Avoid_: Comanda, ordem, venda

**Status do pedido**:
Recebido → Em preparo → Pronto → Finalizado; Cancelado é possível antes de Pronto.

**Fila da cozinha**:
Lista de pedidos não finalizados nem cancelados, em ordem de confirmação, exibida no painel da cozinha.
_Avoid_: KDS (só como nome técnico da tela)

### Canal

**Canal de mensagens**:
Porta do domínio para enviar e receber mensagens de clientes; hoje implementada pelo gateway WhatsApp.

**Conexão WhatsApp**:
Vínculo entre um número de WhatsApp e um restaurante, criado pela leitura de QR code.
