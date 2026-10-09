# Cenários BDD — Fatia R2

- Fonte das regras: [RTM-r2.md](RTM-r2.md) (RN-12..RN-23) · Tríade por funcionalidade: `@principal`, `@variacao`, `@negative`
- Restaurantes de exemplo: **Sabor do Rio** (A) e **Tacacá da Praça** (B). Dados sintéticos.
- Cadastro de referência do Sabor do Rio, usado nos cenários:

| Ingrediente | Unidade | Saldo inicial | Mínimo | Bloqueia venda |
|---|---|---|---|---|
| Tambaqui | g | 10000 | 2000 | não |
| Farinha d'água | g | 5000 | 1000 | não |
| Polpa de cupuaçu | g | 3000 | 500 | sim |
| Copo descartável | un | 200 | 50 | não |
| Queijo coalho | g | 1000 | 200 | não |

| Item / opção | Preço | Ficha técnica |
|---|---|---|
| Tambaqui assado | R$ 45,90 | 400 g Tambaqui + 50 g Farinha |
| Adicional "Queijo coalho" (Tambaqui) | + R$ 4,00 | 60 g Queijo coalho |
| Suco de cupuaçu — 300 ml | R$ 8,90 | 100 g Polpa + 1 Copo |
| Suco de cupuaçu — 500 ml | R$ 12,90 | 160 g Polpa + 1 Copo |

## Ingredientes (RF-12 · RN-12, RN-23)

```gherkin
@BDD-ING-01 @principal @RF-12 @RN-12
Cenário: Admin cadastra ingrediente
  Dado o admin do "Sabor do Rio" autenticado
  Quando cadastra "Tambaqui" com unidade "g", mínimo 2000 e saldo inicial 10000
  Então o ingrediente aparece com saldo 10000 g e situação "ok"
  E o extrato tem uma movimentação do tipo "saldo_inicial" de +10000

@BDD-ING-02 @variacao @RF-12
Cenário: Variação - ingrediente desativado some das listas mas mantém o histórico
  Dado o ingrediente "Queijo coalho" com movimentações
  Quando o admin o desativa
  Então ele não aparece no painel de estoque nem na escolha de ficha técnica
  Mas o extrato dele continua consultável

@BDD-ING-03 @negative @RF-12 @RN-12
Cenário: Rejeição de unidade ou quantidade inválida
  Quando o admin cadastra um ingrediente com <campo> igual a <valor>
  Então recebe 422 e nada é salvo
  Exemplos:
    | campo         | valor |
    | unidade       | kg    |
    | estoque_minimo| -1    |
    | saldo_inicial | 12.5  |

@BDD-ING-04 @negative @RN-23
Cenário: Rejeição de cadastro de ingrediente por quem não é admin
  Quando o atendente ou a cozinha tenta cadastrar um ingrediente
  Então recebe 403
```

## Ficha técnica (RF-13 · RN-13)

```gherkin
@BDD-FT-01 @principal @RF-13 @RN-13
Cenário: Admin define a ficha técnica do item
  Quando o admin define a ficha do "Tambaqui assado" com 400 g de Tambaqui e 50 g de Farinha d'água
  Então o item mostra a ficha com os dois ingredientes
  E deixa de aparecer como "sem ficha" no painel

@BDD-FT-02 @variacao @RF-13 @RN-19
Cenário: Variação - cada opção de variação tem ficha própria
  Dado o "Suco de cupuaçu" com as opções "300 ml" e "500 ml"
  Quando o admin define 100 g de Polpa + 1 Copo para "300 ml" e 160 g de Polpa + 1 Copo para "500 ml"
  Então cada opção mostra a própria ficha

@BDD-FT-03 @negative @RF-13 @RN-13
Cenário: Rejeição de ficha inválida
  Quando o admin salva uma ficha com <problema>
  Então recebe 422 e a ficha anterior continua valendo
  Exemplos:
    | problema                                   |
    | quantidade 0                               |
    | o mesmo ingrediente duas vezes             |
    | ingrediente desativado                     |
    | ingrediente de outro restaurante           |
```

## Entrada de mercadoria (RF-14 · RN-17, RN-23)

```gherkin
@BDD-ENT-01 @principal @RF-14 @RN-17
Cenário: Atendente registra entrada de mercadoria
  Dado o Tambaqui com saldo 1500 g
  Quando o atendente registra entrada de 8000 g de Tambaqui com referência "NF 1234"
  Então o saldo vira 9500 g
  E o extrato mostra a entrada de +8000 com o atendente como autor e saldo após 9500

@BDD-ENT-02 @variacao @RF-14
Cenário: Variação - entrada de vários ingredientes de uma vez
  Quando o admin registra numa só entrada 5000 g de Farinha d'água e 100 Copos
  Então os dois saldos aumentam
  E cada ingrediente ganha a sua movimentação com a mesma referência

@BDD-ENT-03 @negative @RF-14 @RN-23
Cenário: Rejeição de entrada inválida ou sem permissão
  Quando <quem> registra entrada de <quantidade> de Tambaqui
  Então recebe <codigo> e o saldo não muda
  Exemplos:
    | quem     | quantidade | codigo |
    | admin    | 0          | 422    |
    | admin    | -500       | 422    |
    | cozinha  | 1000       | 403    |
```

## Inventário (RF-15 · RN-17)

```gherkin
@BDD-INV-01 @principal @RF-15 @RN-17
Cenário: Admin informa a contagem real e o sistema ajusta
  Dado o Tambaqui com saldo 9500 g no sistema
  Quando o admin informa a contagem de 9100 g com o motivo "contagem semanal"
  Então o saldo vira 9100 g
  E o extrato mostra um ajuste de -400 com o motivo

@BDD-INV-02 @variacao @RF-15
Cenário: Variação - contagem que zera um saldo negativo
  Dado a Polpa de cupuaçu com saldo -200 g
  Quando o admin informa a contagem de 0 com o motivo "conferência"
  Então o ajuste é de +200 e o saldo fica 0

@BDD-INV-03 @negative @RF-15 @RN-23
Cenário: Rejeição de ajuste sem motivo, com contagem negativa ou por atendente
  Quando <quem> informa a contagem <contagem> com motivo <motivo>
  Então recebe <codigo> e nenhuma movimentação é criada
  Exemplos:
    | quem      | contagem | motivo      | codigo |
    | admin     | 9000     | ""          | 422    |
    | admin     | -1       | "contagem"  | 422    |
    | atendente | 9000     | "contagem"  | 403    |
```

## Baixa automática (RF-16 · RN-14, RN-15, RN-17)

```gherkin
@BDD-BX-01 @principal @RF-16 @RN-14
Cenário: Pedido confirmado baixa a ficha técnica
  Dado Tambaqui 10000 g e Farinha d'água 5000 g
  Quando um cliente confirma 2 × Tambaqui assado
  Então o Tambaqui fica com 9200 g e a Farinha com 4900 g
  E cada baixa aparece no extrato ligada ao pedido #1

@BDD-BX-02 @variacao @RF-16 @RN-19 @RN-20
Cenário: Variação - baixa com variação e adicional
  Quando um cliente confirma 1 × Tambaqui assado com adicional Queijo coalho e 2 × Suco de cupuaçu 500 ml
  Então baixam 400 g de Tambaqui, 50 g de Farinha, 60 g de Queijo, 320 g de Polpa e 2 Copos

@BDD-BX-03 @variacao @RF-16 @RN-15
Cenário: Variação - saldo fica negativo e o pedido é aceito
  Dado o Tambaqui com 300 g (não bloqueia venda)
  Quando um cliente confirma 1 × Tambaqui assado
  Então o pedido é criado
  E o Tambaqui fica com -100 g e aparece como "negativo" no painel

@BDD-BX-04 @negative @RN-15 @RN-04
Cenário: Rejeição de item cujo ingrediente "bloqueia venda" acabou
  Dado a Polpa de cupuaçu com 150 g e marcada "bloqueia venda"
  Quando o cliente abre a categoria Bebidas
  Então o Suco de cupuaçu 500 ml não aparece (160 g não cabem)
  Mas o Suco de cupuaçu 300 ml aparece (100 g cabem)

@BDD-BX-05 @negative @RN-14
Cenário: Rejeição de pedido parcial quando a baixa falha
  Dado um carrinho válido no resumo
  Quando a gravação da baixa falha no meio
  Então nenhum pedido é criado e nenhum saldo muda
  E a mesma mensagem pode ser reprocessada quando o gateway a reenviar, criando um único pedido

@BDD-BX-06 @negative @RN-15 @RN-04
Cenário: Rejeição na confirmação quando o ingrediente "bloqueia venda" acabou depois do resumo
  Dado a Polpa de cupuaçu com 200 g, marcada "bloqueia venda"
  E um cliente no resumo com 2 × Suco de cupuaçu 300 ml
  Quando outro pedido baixa 160 g de Polpa antes da confirmação
  E o cliente confirma
  Então nenhum pedido é criado e nenhum saldo muda
  E o robô avisa que o Suco de cupuaçu 300 ml ficou indisponível e volta ao carrinho
```

## Estorno (RF-16 · RN-16)

```gherkin
@BDD-EST-01 @principal @RF-16 @RN-16
Cenário: Cancelamento em "Recebido" devolve o estoque
  Dado o pedido #1 "Recebido" que baixou 800 g de Tambaqui e 100 g de Farinha
  Quando o atendente cancela com motivo "Cliente desistiu"
  Então os saldos voltam ao valor de antes do pedido
  E o extrato mostra o estorno ligado ao pedido #1

@BDD-EST-02 @variacao @RN-16
Cenário: Variação - estorno devolve o que foi baixado, mesmo com ficha alterada depois
  Dado o pedido #1 "Recebido" que baixou 400 g de Tambaqui
  E o admin mudou a ficha do Tambaqui assado para 450 g
  Quando o pedido é cancelado
  Então voltam 400 g, não 450 g

@BDD-EST-03 @negative @RN-16
Cenário: Rejeição de estorno para pedido cancelado em preparo
  Dado o pedido #2 "Em preparo"
  Quando o admin cancela com motivo "Falta de gás"
  Então o pedido é cancelado
  E nenhum ingrediente volta ao estoque
```

## Alertas (RF-17 · RN-18)

```gherkin
@BDD-ALR-01 @principal @RF-17 @RN-18
Cenário: Ingrediente abaixo do mínimo gera alerta
  Dado o Queijo coalho com mínimo 200 g
  Quando o saldo cai para 180 g por causa de um pedido
  Então o painel mostra 1 alerta
  E o Queijo coalho aparece em "abaixo do mínimo"

@BDD-ALR-02 @variacao @RN-18
Cenário: Variação - alertas ordenados por criticidade
  Dado Polpa com saldo -50 g (mínimo 500) e Queijo com 180 g (mínimo 200)
  Quando a cozinha abre o painel de estoque
  Então a Polpa aparece antes do Queijo

@BDD-ALR-03 @negative @RN-18 @RN-23
Cenário: Rejeição de alteração de estoque pela cozinha
  Dado um usuário com papel "cozinha"
  Quando ele consulta o painel de estoque
  Então vê saldos e alertas
  Mas recebe 403 ao tentar registrar entrada, ajuste ou editar ingrediente
```

## Extrato (RF-18 · RN-17)

```gherkin
@BDD-EXT-01 @principal @RF-18 @RN-17
Cenário: Extrato de movimentações por período
  Dado entradas, baixas e um ajuste do Tambaqui na semana
  Quando o admin consulta o extrato de 01/10 a 07/10
  Então vê as movimentações em ordem, cada uma com tipo, quantidade, saldo após, autor e data

@BDD-EXT-02 @variacao @RF-18
Cenário: Variação - a soma das movimentações confere com o saldo
  Dado qualquer sequência de movimentações do Tambaqui
  Então a soma de todas as quantidades do extrato é igual ao saldo atual

@BDD-EXT-03 @negative @RN-17
Cenário: Rejeição de edição ou exclusão de movimentação
  Quando alguém tenta alterar ou apagar uma movimentação pela API
  Então recebe 405 e a movimentação continua igual
```

## Variações e adicionais no robô (RF-19 · RN-19, RN-20, RN-22)

```gherkin
@BDD-VAR-01 @principal @RF-19 @RN-19
Cenário: Cliente escolhe o tamanho antes da quantidade
  Dado o "Suco de cupuaçu" com as opções "1 - 300 ml (R$ 8,90)" e "2 - 500 ml (R$ 12,90)"
  Quando o cliente escolhe o suco, depois "2" e a quantidade "2"
  Então o carrinho tem "2 × Suco de cupuaçu (500 ml) — R$ 25,80"

@BDD-VAR-02 @variacao @RF-19 @RN-20
Cenário: Variação - adicionais somam no preço e separam a linha
  Dado 1 × Tambaqui assado no carrinho
  Quando o cliente adiciona 1 × Tambaqui assado com adicional "Queijo coalho"
  Então o carrinho tem duas linhas: "1 × Tambaqui assado — R$ 45,90" e "1 × Tambaqui assado + Queijo coalho — R$ 49,90"

@BDD-VAR-03 @negative @RN-20
Cenário: Rejeição de adicionais inválidos
  Dado o robô oferecendo os adicionais do Tambaqui
  Quando o cliente envia <entrada>
  Então o robô responde "Opção inválida" e mostra os adicionais de novo
  Exemplos:
    | entrada |
    | 1,1     |
    | 9       |
    | 1,2,3,4,5,6 |

@BDD-VAR-04 @negative @RN-19
Cenário: Rejeição de pedido sem variação obrigatória
  Dado o robô perguntando o tamanho do Suco de cupuaçu
  Quando o cliente envia "0" ou um texto
  Então o robô pede o tamanho de novo e nada entra no carrinho
```

## Observação por item (RF-20 · RN-21, RN-22)

```gherkin
@BDD-OBI-01 @principal @RF-20 @RN-21
Cenário: Cliente põe observação num item do carrinho
  Dado 1 × Tambaqui assado e 1 × Suco de cupuaçu 300 ml no carrinho
  Quando o cliente escolhe "Adicionar observação a um item", o Tambaqui e envia "sem cebola"
  Então o carrinho mostra "1 × Tambaqui assado — obs.: sem cebola"
  E o ticket da cozinha mostra a observação na linha do Tambaqui

@BDD-OBI-02 @variacao @RN-22
Cenário: Variação - observação em parte das unidades separa a linha
  Dado 2 × Tambaqui assado no carrinho, numa só linha
  Quando o cliente escolhe "Adicionar observação a um item", o Tambaqui, a quantidade "1" e envia "sem cebola"
  Então o carrinho tem "1 × Tambaqui assado — obs.: sem cebola" e "1 × Tambaqui assado"

@BDD-OBI-03 @negative @RN-21
Cenário: Rejeição de observação por item com mais de 80 caracteres
  Quando o cliente envia uma observação de 81 caracteres para um item
  Então o robô responde que a observação do item pode ter no máximo 80 caracteres
  E a linha continua sem observação
```

## Isolamento no estoque (RN-01)

```gherkin
@BDD-ISO-04 @negative @RN-01
Cenário: Rejeição de leitura ou alteração de ingrediente de outro restaurante
  Dado o ingrediente "Mandioca" do "Tacacá da Praça"
  Quando o admin do "Sabor do Rio" consulta, edita, lança entrada, ajusta ou pede o extrato desse ingrediente
  Então recebe 404 e o saldo do "Tacacá da Praça" não muda

@BDD-ISO-05 @negative @RN-01
Cenário: Rejeição de baixa cruzada entre restaurantes
  Dado os dois restaurantes com ingredientes de mesmo nome
  Quando um pedido é confirmado no "Sabor do Rio"
  Então só os saldos do "Sabor do Rio" mudam
```

## Não aplicável na R2 (justificado)

- Concorrência entre baixa e entrada no mesmo ingrediente: as duas travam a linha do ingrediente (RT-10); coberto por teste de concorrência no Gate 3, não por cenário de negócio.
- Mudança de ficha com pedidos abertos: o pedido usa a ficha congelada na confirmação (RN-22), coberto por BDD-EST-02.
