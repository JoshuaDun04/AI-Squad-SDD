# Contratos — Fatia R1

- Especificador: ARC-01 / ENG-02 · Fonte: RTM.md, ADR-0001..0006
- Convenções: JSON UTF-8; valores em centavos (`int` estrito); datas ISO 8601 com fuso; ids UUID; erros `{"erro": "<codigo>", "detalhe": "<texto>"}`
- Autenticação do painel: `Authorization: Bearer <jwt>` (RT-02). Recurso de outro restaurante → **404** (RN-01).
- Revisão Gate 3 (08/10/2026): acrescentados `/auth/eu`, `GET /pedidos` (histórico), `POST /whatsapp/desconectar`, `/saude`, 429 no login, 503 ao conectar com gateway fora, 409 ao apagar categoria com itens, convenção de `dia_semana`. Marcados com ★. DEC-07 acrescentou `observacao` ao pedido.

## 1. API (`api`, FastAPI) — painel

| Método e rota | Papéis | Corpo / retorno | Erros | Requisitos |
|---|---|---|---|---|
| `POST /restaurantes` | público | `{nome, admin_email, admin_senha (≥8), fuso?}` → `201 {restaurante_id}` | 409 e-mail já usado, 422 (fuso inválido etc.) | RF-01 |
| `POST /auth/login` | público | `{email, senha}` → `200 {token, papel, restaurante_id}` | 401; ★ 429 após 5 falhas em 15 min (por e-mail+IP, persistido) | RF-02, RT-02 |
| ★ `GET /auth/eu` | todos | `{usuario_id, email, papel, restaurante_id, restaurante_nome, fuso}` | 401 | RF-02 |
| `GET/POST /usuarios` · `PATCH /usuarios/{id}` | admin | `{email, senha, papel}` · `{senha?, papel?, ativo?}` | 403, 404, 409, 422 (★ admin não desativa nem rebaixa a si mesmo) | RF-03 |
| `GET/POST /categorias` · `PATCH/DELETE /categorias/{id}` | admin (GET: todos) | `{nome, ordem, ativa}` | 403, 404, ★ 409 categoria com itens, 422 | RF-04 |
| `GET/POST /itens` · `PATCH /itens/{id}` | admin (GET: todos) | `{categoria_id, nome, descricao, preco_centavos>0, disponivel, ordem}`; `GET ?categoria_id=` | 403, 404, 422 (preço não inteiro, ≤ 0, categoria de outro restaurante) | RF-04, RN-02, RN-04 |
| `GET/PUT /horarios` | admin (GET: todos) | PUT: `[{dia_semana 0-6, abre "HH:MM", fecha "HH:MM"}]`; GET: `{fuso, aberto_agora, proxima_abertura, faixas}` | 422 fecha ≤ abre, ★ dia repetido | RF-05, RN-07 |
| `POST /whatsapp/conectar` | admin | `202 {status:"aguardando_qr"}` | 403, ★ 503 gateway indisponível | RF-06 |
| ★ `POST /whatsapp/desconectar` | admin | `200 {status:"desconectado"}` | 403 | RF-06 |
| `GET /whatsapp/status` | admin | `{status, qr_code_data_url?, atualizado_em?}` | 403 | RF-06 |
| `GET /fila` | cozinha, atendente, admin | `[{pedido_id, numero, status, criado_em, tipo, observacao, itens:[{nome, quantidade}]}]` em ordem de `criado_em`; sem endereço nem telefone | 403 | RF-09, RT-05 |
| ★ `GET /pedidos?data=AAAA-MM-DD` | atendente, admin | pedidos do dia local (padrão: hoje no fuso do restaurante), com `total_centavos` e `pagamento` | 403 | RF-09 (histórico, BDD-COZ-02) |
| `GET /pedidos/{id}` | atendente, admin | pedido completo, com cliente `{nome_perfil, telefone}`, endereço e `observacao` | 403 (cozinha), 404 | RF-09, RN-10 |
| `POST /pedidos/{id}/status` | cozinha, atendente, admin | `{novo_status}` → `200 {status}` | 403, 404, 409 transição inválida, ★ 422 status desconhecido ou "Cancelado" (use /cancelar) | RF-10, RN-09 |
| `POST /pedidos/{id}/cancelar` | atendente, admin | `{motivo (3 a 300 caracteres)}` → `200 {status, motivo}` | 403, 404, 409 após Pronto, 422 sem motivo | RF-11, RN-09 |
| ★ `GET /saude` | público | `{ok: true}` | — | RT-07 |

`dia_semana` segue `datetime.weekday()`: **0 = segunda-feira … 6 = domingo**. Uma faixa por dia, sem virada de meia-noite na R1.

## 2. Gateway → API (webhook)

`POST /canal/webhook` · header `X-Gateway-Token` (RT-03) · 401 se ausente ou inválido · não exposto pelo nginx do painel

```json
{
  "tipo": "mensagem",
  "restaurante_id": "uuid",
  "mensagem_id": "wamid-123",
  "telefone": "5592991234567",
  "nome_perfil": "Maria",
  "texto": "1",
  "recebida_em": "2026-10-06T12:00:00-04:00"
}
```

`telefone`: 8 a 15 dígitos (número, ou identificador LID quando o WhatsApp não informa o número).
Outros `tipo`: `"status_conexao"` com `{restaurante_id, status: "aguardando_qr"|"conectado"|"desconectado", qr_code?}` (`qr_code` é um data URL PNG).
Resposta `200 {"ok": true}` após persistir; mensagem duplicada (`mensagem_id` já visto) → `200` sem efeito (BDD-WA-04); restaurante inexistente → 404.

## 3. API → Gateway

| Método e rota | Corpo | Uso | Respostas |
|---|---|---|---|
| `POST /sessoes/{restaurante_id}` | — | iniciar sessão e gerar QR (RF-06) | 202; 400 id inválido |
| `DELETE /sessoes/{restaurante_id}` | — | desconectar e apagar credenciais | 200 |
| `POST /mensagens` | `{restaurante_id, telefone, texto (≤4096)}` | resposta do robô e avisos de status (RF-07, RF-10, RF-11) | 200; 400 corpo inválido; 409 sessão não conectada |
| `GET /saude` | — | verificação de vida (sem token) | 200 |

Header `X-Gateway-Token` nas duas direções, comparado em tempo constante. O gateway não guarda pedidos nem cardápio.

## 4. Porta de domínio

```python
class CanalMensagens(Protocol):
    def enviar(self, restaurante_id: UUID, telefone: str, texto: str) -> None: ...
    def iniciar_sessao(self, restaurante_id: UUID) -> None: ...
    def encerrar_sessao(self, restaurante_id: UUID) -> None: ...
```

Implementações: `GatewayBaileys` (HTTP para `wa-gateway`) e `CanalEmMemoria` (testes). Falha no envio levanta `ErroCanal`, nunca com telefone ou texto na mensagem.

## 5. Modelo de dados (resumo)

`restaurante(id, nome, fuso)` · `usuario(id, restaurante_id, email, senha_hash, papel, ativo)` · ★ `tentativa_login(id, chave, momento)` · `categoria(id, restaurante_id, nome, ordem, ativa)` · `item(id, restaurante_id, categoria_id, nome, descricao, preco_centavos, disponivel, ordem)` · `horario(restaurante_id, dia_semana, abre, fecha)` · `conexao_whatsapp(restaurante_id, status, ★ qr_code, atualizado_em)` · `cliente(id, restaurante_id, telefone, nome_perfil)` · `conversa(id, restaurante_id, cliente_id, estado, carrinho_json, dados_json, ultima_msg_em)` · `mensagem_processada(restaurante_id, mensagem_id)` · `pedido(id, restaurante_id, cliente_id, numero, data_local, status, tipo, endereco?, pagamento, troco_para_centavos?, total_centavos, motivo_cancelamento?, observacao? (≤140, migração 0002), criado_em)` · `pedido_item(id, pedido_id, item_id, nome, preco_unitario_centavos, quantidade)`

Únicos: `usuario.email` global; `(restaurante_id, data_local, numero)` em pedido; `(restaurante_id, mensagem_id)`; `(restaurante_id, telefone)` em cliente; `(restaurante_id, cliente_id)` em conversa. Esquema criado pela migração Alembic `0001` (ADR-0006).
