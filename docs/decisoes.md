# Registro de decisões (DEC)

DEC-01..DEC-06 foram tomadas antes deste repositório existir e estão citadas no PRD e na RTM. Novas decisões entram aqui.

## DEC-07 — Observação livre: por pedido na R1, por item na R2

- Data: 08/10/2026 · Decisor: PM (delegou a recomendação à squad) · Origem: PRD §4 item 3 [H], pendente desde o Gate 2

**Decisão.** A R1 aceita uma observação livre **por pedido**, opcional, de até 140 caracteres. O cliente adiciona pela opção "3 - Adicionar observação" no resumo, antes de confirmar. A observação aparece em destaque no ticket da cozinha e no detalhe do pedido. A observação **por item** fica para a R2, junto com adicionais e variações, porque depende da ficha técnica.

**Por quê.**
- Pedido saindo errado é a dor DN-01. "Sem cebola" e "bem passado" são o caso mais comum que hoje se perde no texto livre do WhatsApp.
- Como opção no resumo, quem não precisa não ganha nenhuma mensagem a mais.
- Observação por item obrigaria a separar linhas iguais com observações diferentes, o que quebra a regra de somar quantidades (BDD-ROB-03), e se sobrepõe às variações da R2.

**Consequências.** Nova regra RN-11, cenários BDD-OBS-01..03, coluna `pedido.observacao` (migração 0002) e campo `observacao` em `GET /fila` e `GET /pedidos/{id}`. A observação nunca vai para log, porque o cliente pode escrever dado de saúde (ex.: alergia).

## DEC-08 — Variações e adicionais entram na R2, junto com o estoque

- Data: 08/10/2026 · Decisor: PM (delegou a recomendação à squad; **confirmada pelo PM em 10/10/2026**, DEC-09) · Origem: DEC-07, PRD §8 ("sem variações na R1")

**Decisão.** A R2 inclui, além de estoque e ficha técnica, um grupo de variação obrigatório por item (ex.: tamanho), adicionais opcionais e observação por item.

**Por quê.** A ficha técnica precisa saber o que foi vendido de fato: um suco de 500 ml gasta mais polpa que um de 300 ml, e um adicional de queijo baixa queijo. Fazer o estoque antes das variações obrigaria a refazer a ficha da linha do pedido logo em seguida. A observação por item foi adiada da R1 para cá pela DEC-07.

**Consequências.** Escopo maior que o PRD original para a R2 (OBJ-07, RN-19..RN-22, RF-19, RF-20). Fica de fora a variação com mais de um grupo por item. O PM pode recusar ao aprovar o Gate 2 da R2 (pergunta 3 da RTM-r2); nesse caso, as variações viram uma fatia própria logo depois.

## DEC-09 — Aprovação do Gate 2 da R2

- Data: 10/10/2026 · Decisor: PM · Origem: perguntas 1 a 5 da RTM-r2

**Decisões.**
1. **Venda com saldo negativo (RN-15):** aceita como proposta. A venda não é bloqueada por saldo; só os ingredientes marcados "bloqueia venda" tiram itens do robô.
2. **Estorno (RN-16):** aceito. O cancelamento devolve ao estoque só se o pedido ainda não entrou em preparo (status "Recebido").
3. **Variações, adicionais e observação por item na R2 (DEC-08):** aceito.
4. **Entrada de mercadoria (RN-23): só o admin.** A proposta da squad (admin e atendente) foi recusada. O atendente consulta saldos, alertas e extrato, sem alterar.
5. **Até onde vai a R2:** segue o previsto no release train do PRD (§3). A R2 foi além do Gate 1, a pedido do PM, e encerra com este Gate 2 aprovado. Gate 3 (implementação) e Gate 4 (validação) da R2 abrem só quando o PM iniciar um novo objetivo para ela.

**Consequências.** Todas as hipóteses [H] da RTM-r2 viram [C]. RN-23, RF-14, BDD-ENT-01, BDD-ENT-03 e o contrato de `POST /estoque/entradas` passam a aceitar só o admin. ADR-0007..0010 passam de "proposed" para "accepted". Com a R1 no Gate 4 e R2 a R4 especificadas, o release train do OBJ-PDV-001 está cumprido; o que resta da R1 é operacional (build e WhatsApp real na VPS).

## DEC-10 — Preparação para o piloto em campo

- Data: 11/10/2026 · Decisor: PM ("resolver tudo o que puder para começar os testes em campo") · Origem: próximos passos após o Gate 4

**Decisões.**
1. **Horários de status no pedido (RT-14):** o pedido passa a guardar a hora de cada mudança (`em_preparo_em`, `pronto_em`, `finalizado_em`, `cancelado_em`; migração 0005). Sem isso, o piloto não mede o tempo até o preparo nem o tempo de preparo. Não há dado pessoal novo.
2. **Kit de produção:** Caddy na frente do painel com HTTPS automático (`docker-compose.prod.yml`, `deploy/Caddyfile`) e um script único de operação (`deploy/pdv.sh`: instalar, atualizar, verificar, backup, restaurar, relatório). O painel deixa de expor porta própria na internet.
3. **Verificação contínua:** o script confere serviços, HTTPS, webhook fechado, conexão do WhatsApp, telefone em log (RN-10) e disco, e pode avisar no celular pelo ntfy.
4. **Plano do piloto:** ensaio interno com 15 testes no WhatsApp real, depois duas semanas com um restaurante, com métricas e critérios de parada ([plano-piloto.md](operacao/plano-piloto.md)). Os alvos das métricas são hipóteses para o PM confirmar.

**Consequências.** Novo job `producao` no CI (instala como numa VPS, verifica, faz backup, apaga tudo e restaura). Actions do CI atualizadas para v7 (Node 24).

## DEC-11 — O PDV passa a ser um aplicativo Windows instalado no computador do restaurante

- Data: 12/10/2026 · Decisor: PM · Origem: objetivo do PM de distribuir um executável que o dono roda no próprio computador

**Decisões.**
1. **Só Windows**, com instalador `.exe`.
2. **Só o aplicativo:** a implantação em servidor (VPS, Caddy, `deploy/pdv.sh`, Docker Compose) deixa de ser forma de distribuição e sai do repositório. O código da API continua aceitando PostgreSQL, mas o produto usa SQLite.
3. **Banco SQLite embutido**, um arquivo na pasta do usuário do Windows.
4. **Atualização automática pelo GitHub Releases** do repositório.
5. **Um restaurante por instalação:** o primeiro cadastro fecha o cadastro de novos restaurantes naquele computador.

**Consequências.**
- O robô só responde com o computador ligado e com internet. O app abre com o Windows, fica na bandeja, impede que o Windows suspenda o processo e avisa quando o WhatsApp cai; o dono precisa deixar o computador ligado no horário de funcionamento.
- A tela da cozinha acessa o painel pela rede local do restaurante, por HTTP. Senhas trafegam sem criptografia na rede da casa; aceitável para Wi-Fi com senha, registrado como risco RSK-03.
- Backup automático passa a ser responsabilidade do app (diário, guardando 14) e fica no mesmo computador; perda do disco perde os backups (RSK-04). O guia recomenda copiar a pasta de backups para um pendrive ou nuvem própria periodicamente.
- Sem certificado de assinatura de código, o Windows SmartScreen mostra um aviso na primeira instalação (RSK-05). Comprar um certificado resolve.
- Para a atualização automática funcionar sem senha, os releases precisam ser públicos (o repositório JoshuaDun04/AI-Squad-SDD já é público).
- Novas peças: ADR-0011 (aplicativo desktop) e ADR-0012 (SQLite como banco do produto); especificação em [desktop/RTM-desktop.md](desktop/RTM-desktop.md). O DEC-10 (kit de produção na VPS) fica superado; o relatório do piloto passa para dentro do painel.

**Implementação (12/10/2026).**
- `pdv/desktop`: app Electron com bandeja, inicialização com o Windows, supervisão com espera crescente, backup diário e ao sair, restauração, aviso de WhatsApp desconectado e de rede Pública, atualização automática e "Redefinir senha do dono…" (RF-28, acrescentado nesta entrega porque, num computador sem suporte por perto, senha esquecida trancaria o dono fora do próprio restaurante).
- API e robô saem sozinhos se o app cair (sem processo órfão segurando o banco); `instancia.json` na pasta de dados diz onde cada peça está ouvindo, sem segredos.
- Python 3.12.10 embutido, baixado do python.org com a assinatura Sigstore conferida no CI; dependências do `requirements-windows.lock.txt` (mesmas versões do lock principal, com hash).
- CI: os jobs `stack` e `producao` (Docker e VPS) saíram; entraram `app` (serviços orquestrados + e2e no Linux) e `windows` (monta o instalador, instala em silêncio, roda o e2e no app instalado, derruba o app e confere que não sobram processos; publica em Releases quando a tag `v*` é criada).
- Removidos: `pdv/deploy/`, `docker-compose*.yml`, Dockerfiles, configuração do nginx e `docs/operacao/implantacao-vps.md`. Guia novo para o dono: [operacao/instalacao-windows.md](operacao/instalacao-windows.md).
