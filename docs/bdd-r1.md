# Cenários BDD — Fatia R1

- Fonte das regras: [RTM.md](RTM.md) (RN-01..RN-10) · Especificador: BA-04 · Revisor: QA-01 (sequencial)
- Tríade por funcionalidade: `@principal` (fluxo principal), `@variacao` (alternativo válido), `@negative` (exceção/rejeição)
- Dados são exemplos sintéticos; restaurantes de exemplo: **Sabor do Rio** (A) e **Tacacá da Praça** (B)
- Mensagens do robô citadas entre aspas definem o conteúdo funcional; o texto final pode ser ajustado no Gate 3 sem mudar o sentido
- Cobertura: cada cenário tem ao menos um teste marcado com `@pytest.mark.bdd("<ID>")` em `pdv/api/tests/`; conferido por `pdv/api/scripts/verificar_rtm.py`

## Autenticação e papéis (RF-01, RF-02, RF-03 · RN-01 · RT-02)

```gherkin
@BDD-AUT-01 @principal @RF-01 @RF-02
Cenário: Cadastro de restaurante e login do admin
  Dado que não existe restaurante com o e-mail "dono@sabor.com"
  Quando alguém cadastra o restaurante "Sabor do Rio" com admin "dono@sabor.com" e senha "Forte#2026"
  E faz login com essas credenciais
  Então recebe um token com papel "admin" e o restaurante "Sabor do Rio"
  E a senha não é armazenada em texto puro

@BDD-AUT-02 @variacao @RF-03
Cenário: Variação - admin cria usuário da cozinha com acesso restrito
  Dado que o admin do "Sabor do Rio" está autenticado
  Quando cria o usuário "cozinha@sabor.com" com papel "cozinha"
  E esse usuário faz login
  Então ele consegue ver a fila da cozinha
  Mas recebe 403 ao tentar editar o cardápio

@BDD-AUT-03 @negative @RF-02
Cenário: Rejeição de login com senha errada, usuário desativado ou token expirado
  Dado o usuário "atendente@sabor.com"
  Quando tenta acessar a API com <situacao>
  Então recebe 401 e nenhum dado é retornado
  Exemplos:
    | situacao                              |
    | senha incorreta                       |
    | usuário desativado pelo admin         |
    | token emitido há mais de 8 horas      |
```

## Isolamento entre restaurantes (RN-01 · RT-01)

```gherkin
@BDD-ISO-01 @negative @RN-01
Cenário: Rejeição de leitura de pedido de outro restaurante
  Dado que o pedido 7 de hoje pertence ao "Tacacá da Praça"
  Quando o atendente do "Sabor do Rio" pede esse pedido pelo id
  Então recebe 404
  E nenhum campo do pedido é exposto

@BDD-ISO-02 @negative @RN-01
Cenário: Rejeição de alteração de cardápio de outro restaurante
  Dado o item "Tacacá grande" do "Tacacá da Praça"
  Quando o admin do "Sabor do Rio" tenta alterar o preço desse item
  Então recebe 404 e o preço continua o mesmo

@BDD-ISO-03 @negative @RN-01
Cenário: Rejeição de mistura na fila da cozinha entre restaurantes
  Dado pedidos Recebido nos dois restaurantes
  Quando a cozinha do "Sabor do Rio" consulta a fila
  Então só vê pedidos do "Sabor do Rio"
```

## Cardápio (RF-04 · RN-02, RN-04)

```gherkin
@BDD-CAR-01 @principal @RF-04
Cenário: Admin monta o cardápio
  Dado o admin do "Sabor do Rio" autenticado
  Quando cria a categoria "Peixes" e o item "Tambaqui assado" a 4590 centavos
  Então o item aparece na categoria "Peixes" como disponível com preço 4590

@BDD-CAR-02 @variacao @RF-04 @RN-04
Cenário: Variação - item desativado some do robô sem ser apagado
  Dado o item "Tambaqui assado" disponível
  Quando o admin marca o item como indisponível
  Então o item continua no painel com indicação "indisponível"
  E não é listado pelo robô na categoria "Peixes"

@BDD-CAR-03 @negative @RF-04 @RN-02
Cenário: Rejeição de preço inválido
  Quando o admin salva um item com preço <preco>
  Então recebe 422 e o item não é salvo
  Exemplos:
    | preco  |
    | 0      |
    | -100   |
    | 12.90  |

@BDD-CAR-04 @negative @RF-04 @RN-04
Cenário: Rejeição de pedido com item que ficou indisponível durante a conversa
  Dado um cliente com "Tambaqui assado" no carrinho
  Quando o admin desativa o item antes da confirmação
  E o cliente envia a próxima mensagem
  Então o item sai do carrinho
  E o robô avisa "Tambaqui assado ficou indisponível e foi removido do carrinho"
```

## Horário de funcionamento (RF-05 · RN-07)

```gherkin
@BDD-HOR-01 @principal @RF-05 @RN-07
Cenário: Pedido dentro do horário
  Dado que o "Sabor do Rio" abre terça das 11:00 às 23:00 (America/Manaus)
  Quando um cliente confirma um pedido terça às 22:59
  Então o pedido é criado

@BDD-HOR-02 @variacao @RF-05
Cenário: Variação - dia fechado
  Dado que o "Sabor do Rio" não abre às segundas
  Quando um cliente manda "oi" numa segunda às 12:00
  Então o robô responde com o próximo horário de abertura e não mostra o menu

@BDD-HOR-03 @negative @RN-07
Cenário: Rejeição de confirmação após o fechamento
  Dado que o "Sabor do Rio" fecha às 23:00
  E um cliente montou o carrinho às 22:50
  Quando confirma às 23:01
  Então nenhum pedido é criado
  E o robô informa que o restaurante fechou e o próximo horário de abertura
```

## Conexão WhatsApp (RF-06 · RT-03)

```gherkin
@BDD-WA-01 @principal @RF-06
Cenário: Admin conecta o número pelo QR code
  Dado o "Sabor do Rio" com status "desconectado"
  Quando o admin inicia a conexão
  Então o painel mostra um QR code e status "aguardando QR"
  E após a leitura o status vira "conectado"

@BDD-WA-02 @variacao @RF-06
Cenário: Variação - sessão cai e o painel mostra desconectado
  Dado o "Sabor do Rio" "conectado"
  Quando o gateway informa que a sessão foi encerrada
  Então o status vira "desconectado" e o admin pode gerar novo QR code

@BDD-WA-03 @negative @RT-03
Cenário: Rejeição de webhook sem token do gateway
  Quando uma requisição chega ao webhook de mensagens sem "X-Gateway-Token" válido
  Então a API responde 401 e não processa a mensagem

@BDD-WA-04 @negative @RT-03
Cenário: Rejeição de mensagem duplicada
  Dado que a mensagem "wamid-123" já foi processada
  Quando o gateway reenvia "wamid-123"
  Então a API responde 200 sem gerar nova resposta ao cliente nem alterar o carrinho
```

## Robô: navegação e carrinho (RF-07 · RN-04, RN-05, RN-06)

```gherkin
@BDD-ROB-01 @principal @RF-07
Cenário: Cliente navega pelo menu e adiciona item
  Dado o "Sabor do Rio" aberto e conectado
  Quando o cliente envia "oi"
  Então o robô responde com as categorias numeradas
  Quando o cliente envia "1" (Peixes) e depois "1" (Tambaqui assado)
  E informa a quantidade "2"
  Então o carrinho tem 2 × Tambaqui assado e subtotal R$ 91,80
  E o robô oferece "1 - Adicionar mais itens, 2 - Remover item, 3 - Finalizar pedido, 0 - Cancelar"

@BDD-ROB-02 @variacao @RF-07
Cenário: Variação - remover item do carrinho
  Dado um carrinho com 2 × Tambaqui assado e 1 × Suco de cupuaçu
  Quando o cliente escolhe "Remover item" e o número do suco
  Então o carrinho fica só com 2 × Tambaqui assado

@BDD-ROB-03 @variacao @RF-07
Cenário: Variação - mesmo item adicionado duas vezes soma a quantidade
  Dado 2 × Tambaqui assado no carrinho
  Quando o cliente adiciona mais 1 × Tambaqui assado
  Então o carrinho tem uma linha com 3 × Tambaqui assado

@BDD-ROB-04 @negative @RN-05
Cenário: Rejeição de quantidade inválida
  Dado o robô pedindo a quantidade de "Tambaqui assado"
  Quando o cliente envia <entrada>
  Então o robô responde "Envie um número de 1 a 20" e continua pedindo a quantidade
  E o carrinho não muda
  Exemplos:
    | entrada |
    | 0       |
    | 21      |
    | dois    |
    | 2,5     |

@BDD-ROB-05 @negative @RF-07
Cenário: Rejeição de opção inexistente no menu
  Dado o robô mostrando 3 categorias
  Quando o cliente envia "7"
  Então o robô responde "Opção inválida" e repete as categorias

@BDD-ROB-06 @negative @RN-06
Cenário: Rejeição de carrinho expirado por inatividade
  Dado um carrinho com itens e última mensagem do cliente às 12:00
  Quando o cliente envia "3" (finalizar) às 12:31
  Então nenhum pedido é criado
  E o robô avisa que o carrinho expirou e mostra as categorias do início

@BDD-ROB-07 @negative @RF-07 @RN-04
Cenário: Rejeição de escolha feita num menu que mudou
  Dado o robô mostrando "1 - Tambaqui assado, 2 - Pirarucu de casaca"
  Quando o admin desativa o Tambaqui assado
  E o cliente envia "1"
  Então o robô avisa que o cardápio mudou e mostra os itens atualizados
  E não pergunta a quantidade de outro item
```

## Robô: fechamento e pedido (RF-08 · RN-02, RN-03, RN-07, RN-08 · RT-08)

```gherkin
@BDD-PED-01 @principal @RF-08 @RN-02 @RN-03
Cenário: Cliente fecha pedido para retirada com Pix
  Dado um carrinho com 2 × Tambaqui assado (4590) e 1 × Suco de cupuaçu (890)
  Quando o cliente escolhe "Retirada", pagamento "Pix" e confirma o resumo
  Então é criado o pedido número 1 do dia com total 10070 centavos, status "Recebido"
  E cada linha guarda o preço unitário do momento
  E o pedido aparece na fila da cozinha
  E o cliente recebe "Pedido #1 recebido! Total R$ 100,70"

@BDD-PED-02 @variacao @RF-08 @RN-08
Cenário: Variação - entrega com dinheiro e troco
  Dado um carrinho de total 3870 centavos
  Quando o cliente escolhe "Entrega", informa o endereço "Rua 10 de Julho, 500, Centro"
  E escolhe "Dinheiro" com troco para "50"
  Então o pedido é criado com tipo "entrega", endereço informado e troco_para 5000

@BDD-PED-03 @variacao @RT-08 @RN-03
Cenário: Variação - numeração diária e preço congelado
  Dado que o último pedido de ontem do "Sabor do Rio" foi o número 58
  Quando o primeiro pedido de hoje, com Tambaqui a 4590, é confirmado às 00:05 (America/Manaus)
  Então ele recebe o número 1
  Quando o admin muda o preço do Tambaqui assado para 4990
  Então o pedido 1 continua com Tambaqui a 4590 e total inalterado

@BDD-PED-04 @negative @RN-08
Cenário: Rejeição de troco menor que o total
  Dado um carrinho de total 3870 centavos e pagamento "Dinheiro"
  Quando o cliente informa troco para "30"
  Então o robô responde que o troco precisa ser maior ou igual a R$ 38,70 ou "sem troco"
  E nenhum pedido é criado

@BDD-PED-05 @negative @RF-08
Cenário: Rejeição de entrega sem endereço
  Dado o robô pedindo o endereço de entrega
  Quando o cliente envia uma mensagem vazia ou com menos de 10 caracteres
  Então o robô pede o endereço completo de novo

@BDD-PED-06 @negative @RF-08
Cenário: Rejeição de confirmação com carrinho vazio
  Dado um carrinho sem itens
  Quando o cliente escolhe "Finalizar pedido"
  Então o robô informa que o carrinho está vazio e volta às categorias

@BDD-PED-07 @negative @RF-08 @RN-03
Cenário: Rejeição de confirmação com total diferente do resumo mostrado
  Dado o resumo do pedido mostrando "Total: R$ 91,80"
  Quando o admin muda o preço do Tambaqui assado
  E o cliente envia "1" para confirmar
  Então nenhum pedido é criado
  E o robô avisa que os preços mudaram e mostra o resumo com o novo total
  Quando o cliente confirma de novo
  Então o pedido é criado com o novo total
```

## Observação do pedido (RF-08 · RN-11 · DEC-07)

```gherkin
@BDD-OBS-01 @principal @RF-08 @RN-11
Cenário: Cliente adiciona observação antes de confirmar
  Dado o robô mostrando o resumo do pedido
  Quando o cliente escolhe "3 - Adicionar observação" e envia "tambaqui sem cebola"
  Então o resumo mostra "Observação: tambaqui sem cebola"
  Quando o cliente confirma
  Então o pedido guarda a observação
  E a fila da cozinha mostra a observação no ticket

@BDD-OBS-02 @variacao @RF-08 @RN-11
Cenário: Variação - cliente remove a observação
  Dado um resumo com a observação "sem cebola"
  Quando o cliente escolhe "3 - Alterar observação" e envia "0"
  Então o resumo volta sem observação
  E o pedido confirmado não tem observação

@BDD-OBS-03 @negative @RN-11
Cenário: Rejeição de observação com mais de 140 caracteres
  Dado o robô pedindo a observação
  Quando o cliente envia um texto de 141 caracteres
  Então o robô responde que a observação pode ter no máximo 140 caracteres e pede de novo
  E nenhum pedido é criado
```

## Fila da cozinha e status (RF-09, RF-10 · RN-09 · RT-05)

```gherkin
@BDD-COZ-01 @principal @RF-09 @RF-10
Cenário: Cozinha prepara o pedido e o cliente é avisado
  Dado os pedidos #1 (11:10) e #2 (11:12) com status "Recebido"
  Quando a cozinha abre a fila
  Então vê #1 antes de #2
  Quando muda #1 para "Em preparo" e depois para "Pronto"
  Então o cliente do #1 recebe uma mensagem a cada mudança

@BDD-COZ-02 @variacao @RF-10
Cenário: Variação - finalizado sai da fila
  Dado o pedido #1 "Pronto"
  Quando o atendente marca "Finalizado"
  Então #1 sai da fila da cozinha e continua consultável no histórico

@BDD-COZ-03 @negative @RN-09
Cenário: Rejeição de transição de status fora de ordem
  Dado o pedido #1 com status <atual>
  Quando alguém tenta mudar para <novo>
  Então recebe 409, o status continua <atual> e nenhuma mensagem é enviada
  Exemplos:
    | atual      | novo       |
    | Recebido   | Pronto     |
    | Pronto     | Em preparo |
    | Finalizado | Recebido   |

@BDD-COZ-04 @negative @RF-10
Cenário: Rejeição de cancelamento ou leitura de endereço pelo papel cozinha
  Dado um usuário com papel "cozinha" e o pedido de entrega #5 "Recebido"
  Quando tenta cancelar o pedido #5 ou abrir o detalhe com endereço
  Então recebe 403 e o pedido não muda
```

## Cancelamento (RF-11 · RN-09)

```gherkin
@BDD-CAN-01 @principal @RF-11
Cenário: Atendente cancela pedido com motivo
  Dado o pedido #2 "Recebido"
  Quando o atendente cancela com o motivo "Cliente desistiu por telefone"
  Então o status vira "Cancelado", o pedido sai da fila e o cliente é avisado

@BDD-CAN-02 @variacao @RF-11
Cenário: Variação - cancelamento em preparo
  Dado o pedido #3 "Em preparo"
  Quando o admin cancela com motivo "Falta de ingrediente"
  Então o pedido é cancelado e o cliente recebe o motivo

@BDD-CAN-03 @negative @RN-09
Cenário: Rejeição de cancelamento sem motivo ou após pronto
  Quando o atendente tenta cancelar <pedido>
  Então recebe <codigo> e o status não muda
  Exemplos:
    | pedido                          | codigo |
    | #2 Recebido, motivo em branco   | 422    |
    | #4 Pronto, com motivo           | 409    |
```

## LGPD (RN-10 · RT-06)

```gherkin
@BDD-LGPD-01 @principal @RN-10
Cenário: Pedido guarda só os dados necessários
  Quando um pedido de retirada é criado
  Então o cliente tem registrados apenas telefone e nome do perfil
  E o pedido não tem endereço

@BDD-LGPD-02 @negative @RT-06
Cenário: Rejeição de dados pessoais em logs
  Dado o cliente com telefone "5592991234567" e endereço "Rua 10 de Julho, 500"
  Quando ele faz um pedido de entrega e ocorre um erro de envio de mensagem
  Então nenhum log contém "5592991234567" nem "Rua 10 de Julho"
  E o log contém o telefone mascarado "*****-4567"
```

## Não aplicável na R1 (justificado)

- Concorrência de dois atendentes mudando o mesmo pedido: a linha do pedido é travada durante a transição (`SELECT ... FOR UPDATE` no PostgreSQL); a segunda tentativa recebe 409 se a transição já não for válida (coberto por BDD-COZ-03).
- Falha do gateway ao enviar aviso: o status muda mesmo assim e a falha é registrada sem dados pessoais (sem reenvio automático na R1); reenvio fica como pendência para R3.
