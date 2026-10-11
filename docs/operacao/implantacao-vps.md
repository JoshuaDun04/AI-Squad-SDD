# Implantação numa VPS

Roteiro para colocar a R1 no ar com HTTPS, backup diário e alerta no celular. Leva cerca de 30 minutos.

## O que você precisa

- **VPS** com Ubuntu 24.04 (ou Debian 12), 2 GB de RAM, 20 GB de disco e IP público. Qualquer provedor serve.
- **Domínio (opcional).** Sem domínio próprio, use `<ip-com-hífens>.sslip.io` (ex.: `203-0-113-10.sslip.io`), que já aponta para o IP e aceita certificado HTTPS. Com domínio próprio, crie um registro `A` apontando para o IP da VPS antes de instalar.
- **Número de WhatsApp dedicado** ao restaurante (um chip só para isso) e um celular com esse WhatsApp para ler o QR code. Não use seu número pessoal: a integração é não oficial e o número pode ser bloqueado (RSK-01).

## 1. Preparar o servidor

```bash
ssh root@IP_DA_VPS
apt update && apt upgrade -y
adduser pdv && usermod -aG sudo pdv          # usuário de trabalho
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw allow 443/udp && ufw --force enable
curl -fsSL https://get.docker.com | sh        # Docker + Compose
usermod -aG docker pdv
apt install -y git
exit
```

Entre de novo como `pdv` (`ssh pdv@IP_DA_VPS`).

## 2. Baixar o código

```bash
sudo mkdir -p /opt/pdv-restaurantes && sudo chown pdv: /opt/pdv-restaurantes
git clone https://github.com/JoshuaDun04/AI-Squad-SDD.git /opt/pdv-restaurantes
cd /opt/pdv-restaurantes/pdv
```

Repositório privado: crie um token de acesso no GitHub (somente leitura do repositório) e use-o como senha no `git clone`.

## 3. Instalar

```bash
./deploy/pdv.sh instalar
```

O script pergunta o domínio (e sugere o endereço sslip.io), gera segredos fortes no `.env`, constrói as imagens, sobe tudo e roda a verificação. O resultado esperado termina em `Tudo certo.`, com um aviso de "WhatsApp nunca conectado".

**Guarde uma cópia do `.env` em lugar seguro.** Sem ele, os backups não servem em outro servidor.

## 4. Primeiro acesso

Abra `https://SEU_DOMINIO`:

1. **Cadastre o restaurante** (e-mail e senha do dono).
2. **Cardápio:** categorias e itens com preço.
3. **Horários:** dias e faixas de funcionamento.
4. **Equipe:** acesso da cozinha (tablet ou TV com navegador) e dos atendentes.
5. **WhatsApp:** "Gerar QR code" e leia no celular do restaurante (Configurações → Aparelhos conectados → Conectar um aparelho).

Rode `./deploy/pdv.sh verificar` de novo: o aviso do WhatsApp deve virar `WhatsApp conectado: 1 restaurante(s)`.

## 5. Agendar backup e alerta

```bash
crontab -e   # cole o conteúdo de deploy/crontab.exemplo, ajustando o caminho e o tópico
```

- **Backup** todo dia às 03:30, em `pdv/backups/` (guarda os 14 últimos).
- **Verificação** a cada 10 minutos. Se algo falhar (serviço parado, WhatsApp desconectado, telefone no log, disco cheio), chega um aviso no celular pelo app **ntfy**: instale o app, inscreva-se num tópico com nome difícil de adivinhar e use o mesmo nome em `ALERTA_URL`.

Os backups têm dados pessoais dos clientes. Para ter cópia fora da VPS, baixe-os por `scp` para um disco criptografado; não suba para serviços abertos.

## Operação do dia a dia

| Tarefa | Comando (dentro de `/opt/pdv-restaurantes/pdv`) |
|---|---|
| Ver se está tudo bem | `./deploy/pdv.sh verificar` |
| Números do piloto | `./deploy/pdv.sh relatorio 7` |
| Atualizar para a versão nova do repositório | `./deploy/pdv.sh atualizar` (faz backup antes) |
| Backup manual | `./deploy/pdv.sh backup` |
| Restaurar | `./deploy/pdv.sh restaurar backups/pdv-AAAAMMDD-HHMMSS.dump backups/sessoes-AAAAMMDD-HHMMSS.tgz` |
| Ver logs | `./deploy/pdv.sh logs api` (ou `wa-gateway`, `web`, `caddy`) |

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Navegador avisa certificado inválido | DNS ainda não aponta para a VPS ou portas 80/443 fechadas | `dig +short SEU_DOMINIO` deve mostrar o IP; confira o `ufw` e o firewall do provedor; `./deploy/pdv.sh logs caddy` |
| QR code não aparece | Gateway reiniciando | Aguarde 30 s e clique de novo; `./deploy/pdv.sh logs wa-gateway` |
| Verificação acusa "WhatsApp desconectado" | Sessão encerrada no celular ou pelo WhatsApp | Painel → WhatsApp → Gerar QR code de novo |
| Robô não responde, painel diz conectado | Fora do horário de funcionamento ou cardápio sem itens disponíveis | Confira Horários e Cardápio; mande "oi" de outro número |
| Verificação acusa "telefone nos logs" | Algum caminho de log vazou dado pessoal (RN-10) | Não ignore: copie o trecho do log sem compartilhar o número e abra um item para a squad |
| Disco acima de 80% | Backups ou imagens antigas | `docker system prune -f`; reduza `BACKUP_MANTER` |
