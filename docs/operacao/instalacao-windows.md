# Guia de instalação — PDV Restaurantes para Windows

Para o dono do restaurante. Em uns 20 minutos o robô do WhatsApp está respondendo e os pedidos caem na tela da cozinha.

## O que você precisa

- Um computador com **Windows 10 ou 11 (64 bits)**, 4 GB de memória e 1 GB livre no disco. Ele fica no restaurante e fica **ligado no horário de funcionamento**: com o computador desligado, o robô não responde.
- **Internet** nesse computador.
- Um **número de WhatsApp só para os pedidos**, num celular que fica com o restaurante. Use um número novo ou um chip separado: o WhatsApp pode bloquear números que usam robô, e é melhor que isso nunca aconteça com o seu número pessoal.
- Para a cozinha: um **tablet, notebook ou TV com navegador**, no **mesmo Wi-Fi** do computador.

## 1. Instalar

1. Baixe o arquivo `PDV-Restaurantes-Setup-<versão>.exe` na página de versões: <https://github.com/JoshuaDun04/AI-Squad-SDD/releases/latest>.
2. Abra o arquivo. O Windows pode mostrar **"O Windows protegeu o computador"**. Isso acontece porque o instalador ainda não tem assinatura digital paga. Clique em **Mais informações** e depois em **Executar assim mesmo**.
3. O Windows pergunta se o app pode **fazer alterações** (é a liberação no firewall para o tablet da cozinha). Clique em **Sim**.
4. Pronto: o PDV abre sozinho, cria um atalho na área de trabalho e passa a **abrir junto com o Windows**.

## 2. Primeiro uso

1. Na primeira vez, o PDV mostra a tela **Cadastrar restaurante**. Preencha o nome, o seu e-mail e uma senha de pelo menos 8 caracteres. Esse e-mail e essa senha são o acesso do dono; guarde bem.
2. **WhatsApp:** no menu, abra **WhatsApp** e clique em **Gerar QR code**. No celular do restaurante: WhatsApp → **Aparelhos conectados** → **Conectar um aparelho** → aponte para o QR. Em até 30 segundos aparece **Conectado**.
3. **Cardápio:** crie as categorias (ex.: Peixes, Bebidas) e os itens com preço.
4. **Horários:** marque os dias e horários de funcionamento. Fora deles, o robô avisa quando o restaurante abre.
5. **Equipe:** crie o usuário da **cozinha** e, se tiver, do **atendente**.
6. Mande um "oi" de outro celular para o número do restaurante e faça um pedido de teste.

## 3. Tela da cozinha (tablet)

1. No PDV, abra **Equipe**: o endereço da cozinha aparece no topo, algo como `http://192.168.0.10:8080`. Ele também está no ícone do PDV perto do relógio (clique com o botão direito → **Endereço da cozinha**, que copia o endereço).
2. No tablet, conectado ao mesmo Wi-Fi, abra o navegador, digite esse endereço e entre com o usuário da cozinha.
3. Se o tablet não abrir a página:
   - Confira se ele está no mesmo Wi-Fi do computador.
   - No computador: **Configurações → Rede e Internet → (sua rede) → Perfil de rede: Privada**. O Windows costuma marcar redes novas como "Pública", e aí bloqueia o tablet. O PDV mostra um aviso quando isso acontece.
   - O endereço pode mudar se o roteador trocar o IP do computador. Veja de novo em **Equipe**. Para não mudar mais, peça a quem cuida da sua internet para "fixar o IP" do computador no roteador.

## 4. No dia a dia

- **Fechar a janela não desliga o robô.** O PDV continua rodando perto do relógio (ícone verde). Para abrir de novo, clique no ícone.
- **Sair de verdade:** botão direito no ícone → **Sair**. O PDV pergunta antes, porque enquanto estiver fechado ninguém recebe resposta no WhatsApp.
- **Não deixe o computador dormir.** O PDV impede que o Windows o suspenda, mas confira em **Configurações → Sistema → Energia** que a tela pode apagar, mas o computador **nunca entra em suspensão** enquanto estiver na tomada. Em notebook, ajuste também "ao fechar a tampa: não fazer nada".
- **Avisos:** o Windows mostra uma notificação quando o WhatsApp desconecta ou quando algo interno para. Se o WhatsApp cair, abra o painel → **WhatsApp** e leia o QR de novo.
- **Relatório:** em **Relatório**, veja pedidos por dia, tempo de preparo, horários de pico, cancelamentos e itens mais pedidos.

## 5. Backup

- O PDV faz **backup sozinho uma vez por dia** e **ao sair**, guardando os 14 mais recentes.
- Para fazer na hora: ícone → **Fazer backup agora**.
- Os backups ficam no próprio computador. **Uma vez por semana, copie a pasta de backups para um pendrive ou para a sua nuvem** (Google Drive, OneDrive): se o computador quebrar, é essa cópia que salva os seus dados. Para achar a pasta: ícone → **Abrir pasta de dados** → pasta `backups`.
- Os backups têm nomes, telefones e endereços dos clientes. Guarde a cópia num lugar só seu.

**Restaurar** (só se precisar voltar os dados): ícone → **Restaurar backup…** → escolha o arquivo. Pedidos feitos depois daquele backup somem; antes de trocar, o PDV guarda uma cópia dos dados atuais.

**Trocar de computador:** instale o PDV no computador novo, feche o cadastro sem preencher, use **Restaurar backup…** com o backup mais recente do computador antigo e leia o QR do WhatsApp de novo.

## 6. Atualizações

O PDV procura versão nova sozinho (ao abrir e a cada 6 horas) e baixa em segundo plano. Quando estiver pronta, aparece um aviso: ela é instalada da próxima vez que o PDV fechar, ou na hora, se você clicar no aviso. Prefira fazer isso fora do horário de pedidos. Para conferir: ícone → **Verificar atualizações**.

## 7. Quando algo dá errado

| O que acontece | O que fazer |
|---|---|
| Robô não responde | O computador está ligado e com internet? O ícone do PDV está perto do relógio? Abra o painel → WhatsApp: se não estiver "Conectado", leia o QR de novo |
| Aviso "precisa de atenção" | Ícone → **Tentar iniciar de novo**. Se repetir, reinicie o computador |
| Tablet da cozinha não abre | Veja a seção 3 (mesmo Wi-Fi, rede Privada, endereço atualizado) |
| "Não foi possível iniciar o PDV" | Clique em **Tentar de novo**. Se continuar, envie ao suporte a pasta `logs` (ícone → **Abrir pasta de dados**) |
| Esqueci a senha do dono | No computador do restaurante: ícone → **Redefinir senha do dono…**, com o e-mail do dono e uma senha nova. Quem estava com o painel aberto precisa entrar de novo |

A pasta `logs` não tem telefones, endereços nem observações dos clientes, então pode ser enviada ao suporte. **Nunca envie** o arquivo `segredos.json` nem a pasta `backups`.

## 8. Desinstalar

**Configurações → Aplicativos → PDV Restaurantes → Desinstalar.** Os dados (banco, backups, sessão do WhatsApp) continuam em `%APPDATA%\PDV Restaurantes`, para o caso de reinstalar. Para apagar tudo, apague essa pasta depois de desinstalar (e guarde um backup antes, se quiser).

## Onde ficam as coisas

| O quê | Onde |
|---|---|
| Programa | `%LOCALAPPDATA%\Programs\` (pasta do PDV Restaurantes) |
| Dados | `%APPDATA%\PDV Restaurantes` |
| Banco de dados | `pdv.sqlite` na pasta de dados |
| Backups | `backups\` na pasta de dados |
| Sessão do WhatsApp | `whatsapp\` na pasta de dados |
| Registros para suporte | `logs\` na pasta de dados |
