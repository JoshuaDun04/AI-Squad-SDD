---
status: accepted
---
# Robô de menu guiado como máquina de estados persistida no banco

A conversa com o cliente é uma máquina de estados (SAUDACAO → CATEGORIAS → ITENS → QUANTIDADE → CARRINHO → TIPO → ENDERECO → PAGAMENTO → TROCO → CONFIRMACAO) implementada em Python puro no domínio, com estado e carrinho persistidos na tabela `conversa`. Escolhido em vez de manter estado em memória do gateway para sobreviver a reinício, permitir testes unitários sem WhatsApp e manter regras só na API. Expiração de 30 min (RN-06) é avaliada na chegada da próxima mensagem, sem job agendado.

## Implementação (Gate 3)

- `pdv_api/dominio/robo.py`: função pura `processar(conversa, texto, contexto) -> Resultado`. Estados reais: INICIO (saudação), CATEGORIAS, ITENS, QUANTIDADE, CARRINHO, REMOVER, TIPO, ENDERECO, PAGAMENTO, TROCO, CONFIRMACAO.
- O carrinho guarda só `item_id`, nome e quantidade; o preço vem sempre do cardápio vigente, então o pedido congela o preço do momento da confirmação (RN-03).
- Fora do horário, qualquer mensagem reinicia a conversa e informa a próxima abertura (RN-07). Se um item fica indisponível durante o fechamento, o cliente volta ao carrinho para revisar (RN-04).
