# Cenários BDD — Aplicativo Windows

- Fonte das regras: [RTM-desktop.md](RTM-desktop.md) · Tríade: `@principal`, `@variacao`, `@negative`
- Cenários da API têm teste com `@pytest.mark.bdd("<ID>")`; cenários do app Electron têm o ID no título do teste em `pdv/desktop/test` (ex.: `[BDD-PNL-01]`)

## Instalação e restaurante único (RF-21 · RN-24)

```gherkin
@BDD-INS-01 @principal @RF-21 @RN-24
Cenário: Primeiro uso cadastra o restaurante e fecha o cadastro
  Dado uma instalação nova, sem restaurante
  Quando o painel consulta a instalação
  Então o cadastro está aberto
  Quando o dono cadastra "Sabor do Rio"
  Então o cadastro passa a estar fechado e o painel mostra só o login

@BDD-INS-02 @variacao @RF-23
Cenário: Variação - a instalação informa o endereço para a tela da cozinha
  Dado o app rodando no computador de IP 192.168.0.10
  Quando o painel consulta a instalação
  Então recebe o endereço "http://192.168.0.10:8080" para abrir no tablet da cozinha

@BDD-INS-03 @negative @RN-24
Cenário: Rejeição de segundo restaurante na mesma instalação
  Dado que "Sabor do Rio" já está cadastrado
  Quando alguém tenta cadastrar "Tacacá da Praça"
  Então recebe 409 "restaurante_ja_cadastrado" e nada é criado
```

## Servidor do painel na rede local (RF-23 · RT-18)

```gherkin
@BDD-PNL-01 @principal @RF-23
Cenário: Tablet da cozinha abre o painel pela rede
  Quando um aparelho da rede pede "/"
  Então recebe o painel com os cabeçalhos de segurança
  E "/api/saude" é repassado para a API

@BDD-PNL-02 @variacao @RF-23
Cenário: Variação - rotas do painel funcionam ao recarregar
  Quando um aparelho pede "/qualquer/rota" que não é arquivo
  Então recebe o index.html do painel

@BDD-PNL-03 @negative @RT-18
Cenário: Rejeição de acesso ao webhook interno e a arquivos fora do painel
  Quando um aparelho da rede pede "/api/canal/webhook" ou "/../segredos.json"
  Então recebe 404 e nada é repassado para a API
```

## Backup e restauração (RF-24 · RN-25)

```gherkin
@BDD-BKP-01 @principal @RF-24
Cenário: Backup e restauração recuperam os dados
  Dado um restaurante com cardápio e um pedido
  Quando o app faz backup
  E o banco perde os dados
  E o dono restaura esse backup
  Então o restaurante, o cardápio e o pedido voltam

@BDD-BKP-02 @variacao @RF-24
Cenário: Variação - só os backups mais recentes são guardados
  Dado 16 backups na pasta
  Quando o app faz um backup novo com limite de 14
  Então restam os 14 mais recentes

@BDD-BKP-03 @negative @RF-24
Cenário: Rejeição de arquivo que não é backup válido
  Quando o dono tenta restaurar um arquivo que não é um banco do PDV
  Então a restauração é recusada e o banco atual continua intacto
```

## Relatório do piloto (RF-27 · RN-10)

```gherkin
@BDD-REL-01 @principal @RF-27
Cenário: Admin vê os números do piloto
  Dado pedidos de hoje com horários de preparo
  Quando o admin pede o relatório de 7 dias
  Então vê pedidos, finalizados, cancelados, ticket médio e tempos medianos

@BDD-REL-02 @variacao @RF-27
Cenário: Variação - período e cancelados
  Dado pedidos de hoje e de 10 dias atrás, um deles cancelado
  Quando o admin pede o relatório de 7 dias
  Então só entram os pedidos de hoje e o cancelado não entra no ticket médio

@BDD-REL-03 @negative @RF-27 @RN-10
Cenário: Rejeição de relatório para quem não é admin ou com período inválido
  Quando a cozinha ou o atendente pede o relatório, ou o admin pede 0 dias
  Então recebe 403 ou 422
  E nenhum relatório traz telefone ou endereço de cliente
```

## Aplicativo (RF-22, RF-25, RF-26 · RT-19)

```gherkin
@BDD-APP-01 @principal @RF-22 @RT-19
Cenário: O app sobe os serviços e mantém o robô rodando
  Quando o app abre
  Então a API, o gateway e o servidor do painel ficam no ar
  E fechar a janela não para nenhum deles

@BDD-APP-02 @variacao @RT-19
Cenário: Variação - serviço que cai é reiniciado
  Dado a API rodando
  Quando o processo da API termina inesperadamente
  Então o app reinicia a API com espera crescente e avisa na bandeja

@BDD-APP-03 @negative @RF-26
Cenário: Rejeição silenciosa de falha permanente
  Dado um serviço que cai repetidamente
  Quando passa do limite de reinícios
  Então o app para de tentar, mostra o serviço como parado e avisa o dono
```

## Senha do dono esquecida (RF-28 · RN-24)

```gherkin
@BDD-SEN-01 @principal @RF-28
Cenário: Dono redefine a senha no computador do restaurante
  Dado que o dono esqueceu a senha e errou o login algumas vezes
  Quando, no menu da bandeja, ele usa "Redefinir senha do dono…" com o e-mail do dono e uma senha nova
  Então ele entra com a senha nova, a antiga deixa de valer e a senha não aparece em nenhuma saída

@BDD-SEN-02 @variacao @RF-28 @RT-17
Cenário: Variação - sessões abertas caem ao redefinir a senha
  Dado o painel aberto com a sessão do dono
  Quando a senha do dono é redefinida no computador
  Então a sessão aberta deixa de valer e é preciso entrar de novo

@BDD-SEN-03 @negative @RF-28
Cenário: Rejeição de redefinição para quem não é dono ou com senha fraca
  Quando a redefinição usa um e-mail que não é de administrador, uma senha com menos de 8 caracteres ou um banco inexistente
  Então nada muda e o dono continua entrando com a senha antiga
```
