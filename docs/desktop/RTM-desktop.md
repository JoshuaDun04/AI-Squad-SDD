# RTM — PDV Restaurantes · Aplicativo Windows (OBJ-PDV-003)

- Objetivo: distribuir a R1 como aplicativo instalado no computador do restaurante · Fonte: [DEC-11](../decisoes.md), ADR-0011, ADR-0012
- Continua valendo tudo da R1 ([RTM.md](../RTM.md)): RN-01..RN-11, RF-01..RF-11, RT-01..RT-08, RT-14
- Cenários: [bdd-desktop.md](bdd-desktop.md) · Verificação: `python pdv/api/scripts/verificar_rtm.py` (cobre bdd-r1 e bdd-desktop; cenários do app Electron são conferidos nos testes de `pdv/desktop/test`)

## Dores e objetivos

- **DN-06 (Custo de entrada), aprofundada:** além de não pagar integração oficial, o dono não quer pagar nem administrar servidor.
- **OBJ-08 (Instalar e usar sem técnico):** o dono instala com um `.exe`, cadastra o restaurante e começa a receber pedidos sem abrir terminal.

## Requisitos de negócio

- **RN-24 (Restaurante único):** cada instalação atende um restaurante. Depois do primeiro cadastro, novos cadastros são recusados.
- **RN-25 (Dados no computador do restaurante):** banco, sessões do WhatsApp, backups e logs ficam na pasta do usuário do Windows; nada é enviado para fora além das mensagens do WhatsApp e da consulta de atualização.

## Requisitos funcionais

- **RF-21 (Instalação e primeiro uso):** instalador Windows em português; ao abrir pela primeira vez, o painel mostra o cadastro do restaurante; depois, só o login.
- **RF-22 (Funcionamento contínuo):** o app abre com o Windows e fica na bandeja; fechar a janela não para o robô; "Sair" pede confirmação avisando que o robô para.
- **RF-23 (Tela da cozinha na rede local):** outros aparelhos da mesma rede abrem o painel em `http://<ip-do-computador>:8080`; o endereço aparece no painel e no menu da bandeja. O instalador cria a regra do Firewall do Windows só para rede privada, e o app avisa quando a rede do computador está marcada como Pública.
- **RF-24 (Backup e restauração):** backup automático diário e ao sair, guardando os 14 mais recentes; "Fazer backup agora" e "Restaurar backup…" no menu da bandeja, com confirmação.
- **RF-25 (Atualização automática):** o app procura versão nova no GitHub Releases ao abrir e a cada 6 horas, baixa em segundo plano e instala quando o app for reiniciado, com aviso.
- **RF-26 (Aviso de WhatsApp desconectado):** notificação do Windows e ícone da bandeja indicam quando o WhatsApp do restaurante desconecta ou um serviço interno para.
- **RF-27 (Relatório do piloto no painel):** o admin vê pedidos por dia, tempos de preparo, horários de pico, motivos de cancelamento e itens mais pedidos, por período.
- **RF-28 (Senha do dono esquecida):** no computador do restaurante, o menu da bandeja permite definir uma senha nova para o e-mail do dono; as sessões abertas caem. Quem tem acesso ao computador já tem acesso aos dados, então não há segunda verificação.

## Requisitos técnicos

- **RT-15 (Empacotamento):** Electron 44 + electron-builder (NSIS) + electron-updater; API em Python 3.12 embutido; gateway executado pelo Node do Electron (ADR-0011).
- **RT-16 (SQLite):** WAL, `foreign_keys`, `busy_timeout`, `BEGIN IMMEDIATE`; migrações Alembic aplicadas ao abrir (ADR-0012).
- **RT-17 (Segredos locais):** `JWT_SECRET` e `GATEWAY_TOKEN` gerados na primeira execução e guardados na pasta de dados, legíveis só pelo usuário do Windows.
- **RT-18 (Superfície de rede):** API e gateway só em `127.0.0.1`; o servidor do painel é o único na rede local, com os cabeçalhos de segurança do nginx anterior e `/api/canal/*` respondendo 404.
- **RT-19 (Supervisão):** processo filho que cai é reiniciado com espera crescente (1, 2, 4, 8, 16, 30 s); mais de 6 quedas em 10 minutos deixam o serviço parado e o dono é avisado, com "Tentar iniciar de novo" na bandeja. Se o próprio app cair, a API e o robô saem sozinhos (a entrada padrão fecha), sem processo órfão segurando o banco.

## Matriz de rastreabilidade

| ID Dor | ID Objetivo | ID Requisito Negócio | ID Requisito Funcional | ID Requisito Técnico | Cobertura BDD (Tríade) | Evidência |
|---|---|---|---|---|---|---|
| DN-06 | OBJ-08 | RN-24 | RF-21 | RT-17 | BDD-INS-01 @principal; BDD-INS-02 @variacao; BDD-INS-03 @negative | pytest (`test_instalacao.py`) |
| DN-02 | OBJ-02, OBJ-08 | RN-01 | RF-23 | RT-18 | BDD-PNL-01 @principal; BDD-PNL-02 @variacao; BDD-PNL-03 @negative | node:test (`pdv/desktop/test`) |
| DN-06 | OBJ-08 | RN-25, RN-10 | RF-24 | RT-16 | BDD-BKP-01 @principal; BDD-BKP-02 @variacao; BDD-BKP-03 @negative | pytest (`test_backup.py`) |
| DN-01, DN-02 | OBJ-01, OBJ-02 | RN-10 | RF-27 | RT-14, RT-16 | BDD-REL-01 @principal; BDD-REL-02 @variacao; BDD-REL-03 @negative | pytest (`test_relatorio.py`) |
| DN-06 | OBJ-08 | RN-24 | RF-28 | RT-17 | BDD-SEN-01 @principal; BDD-SEN-02 @variacao; BDD-SEN-03 @negative | pytest (`test_backup.py`) |
| DN-06 | OBJ-08 | — | RF-22, RF-25, RF-26 | RT-15, RT-19 | BDD-APP-01 @principal; BDD-APP-02 @variacao; BDD-APP-03 @negative | node:test (`supervisor.test.js`, `orquestrador.test.js` com API, robô e painel reais) + job `windows` do CI: instala o `.exe` em silêncio, roda o e2e no app instalado e derruba o app para conferir que não sobram processos |

## Riscos novos

- **RSK-03:** painel na rede local por HTTP; quem estiver no Wi-Fi do restaurante pode capturar senhas. Mitigação: Wi-Fi com senha; HTTPS local fica para depois.
- **RSK-04:** backups no mesmo disco. Mitigação: guia orienta cópia periódica para pendrive ou nuvem própria.
- **RSK-05:** instalador sem assinatura de código gera aviso do SmartScreen. Mitigação: certificado de assinatura antes de distribuir em escala.
- **RSK-06:** computador desligado ou sem internet deixa clientes sem resposta. Mitigação: o robô volta a responder sozinho ao ligar; o guia orienta deixar ligado no horário de funcionamento.
- **RSK-07:** Windows marca redes novas como Públicas, e a regra do firewall vale só para rede privada; a cozinha não abre o painel. Mitigação: o app detecta e avisa com o atalho para a configuração; o guia mostra o passo.
