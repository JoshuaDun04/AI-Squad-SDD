---
status: accepted
---
# Gateway WhatsApp não oficial em TypeScript, atrás da porta CanalMensagens

O PM aceitou usar biblioteca não oficial (DEC-02, riscos RSK-01 e RSK-02) para ter custo zero no MVP. As bibliotecas maduras são Node.js, então o transporte vive num serviço `wa-gateway` em TypeScript com Baileys, sem nenhuma regra de negócio: ele só mantém a sessão por restaurante, expõe o QR code e repassa mensagens para a API Python por webhook. O domínio conhece apenas a porta `CanalMensagens`; trocar pela API oficial (Cloud API) é escrever outro adaptador.

## Consequences

- A sessão do WhatsApp exige processo sempre ligado e volume persistente para as credenciais; não roda em serverless.
- O gateway autentica-se na API com segredo compartilhado (header `X-Gateway-Token`), e a API autentica-se no gateway do mesmo jeito.
- Mensagens recebidas podem chegar duplicadas; a API deduplica pelo `mensagem_id` do WhatsApp.

## Implementação (Gate 3)

- Baileys 7 (release candidate). Contatos que chegam só com identificador LID (sem número) são aceitos; o gateway grava o par identificador → JID LID em `DATA_DIR/contatos/<restaurante_id>.json` (permissão 600, escrita atômica) para responder mesmo depois de reiniciar. O arquivo é apagado quando o número é desconectado. Contatos com número normal não são gravados.
- O gateway repete o webhook em falha 5xx/rede (até 4 tentativas, espera exponencial); a deduplicação da API torna isso seguro.
