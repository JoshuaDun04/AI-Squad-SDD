# PDV Restaurantes — R1

Pedidos pelo WhatsApp entrando direto na fila da cozinha, para vários restaurantes na mesma instalação.

O cliente conversa com um robô de menu numerado (categorias → itens → quantidade → carrinho → retirada ou entrega → pagamento → confirmação). O pedido aparece no painel da cozinha em poucos segundos, e cada mudança de status avisa o cliente no WhatsApp.

## O que tem aqui

```
docs/                 governança SDD: RTM, cenários BDD, contratos, ADRs, parecer do Gate 4
CONTEXT.md            glossário do domínio
pdv/
  api/                Python · FastAPI · SQLAlchemy · PostgreSQL — todas as regras de negócio
  wa-gateway/         TypeScript · Baileys — só transporte do WhatsApp (sessão, QR, mensagens)
  web/                React · TypeScript — painel do admin, do atendente e da cozinha
  docker-compose.yml  api + wa-gateway + web + db
```

## Subir numa VPS

Requisitos: Docker com Compose v2, 1 GB de RAM livre, um número de WhatsApp dedicado ao restaurante.

```bash
cd pdv
cp .env.example .env
# troque os três segredos do .env (openssl rand -hex 32 gera um bom valor)
docker compose up -d --build
```

O painel fica em `http://<ip-da-vps>:8080`. No primeiro acesso, use "Cadastre seu restaurante". Depois:

1. **Cardápio**: crie categorias e itens.
2. **Horários**: marque os dias e horários de funcionamento.
3. **WhatsApp**: gere o QR code e leia com o celular do restaurante (Aparelhos conectados).
4. **Equipe**: dê acesso à cozinha e aos atendentes.

A API aplica as migrações do banco sozinha ao subir. Coloque um proxy com HTTPS (Caddy, Nginx) na frente da porta 8080 antes de usar em produção.

## Desenvolver

```bash
# API
cd pdv/api
pip install -r requirements.lock.txt pytest pytest-cov
python -m pytest                                   # SQLite em memória
TEST_DATABASE_URL=postgresql+psycopg://pdv:pdv@localhost/pdv_test python -m pytest   # PostgreSQL
python scripts/verificar_rtm.py                    # cobertura BDD + regras de isolamento
DATABASE_URL=... alembic upgrade head              # migrações
DATABASE_URL=... JWT_SECRET=... GATEWAY_TOKEN=... uvicorn pdv_api.main:criar_app_do_ambiente --factory --reload

# Gateway
cd pdv/wa-gateway && npm ci && npm test && npm run build

# Painel (proxy de /api para localhost:8000)
cd pdv/web && npm ci && npm test && npm run dev
```

Toda mudança de modelo precisa de migração nova: `alembic revision --autogenerate -m "..."` e depois `alembic check`.

## Regras que valem para qualquer mudança

- Nenhuma rota consulta o banco direto; só repositórios que recebem `restaurante_id` (ADR-0001). O verificador falha se isso for quebrado.
- Dinheiro é sempre `int` em centavos (ADR-0004).
- Regra de negócio fica na API, nunca no gateway (ADR-0002).
- Telefone e endereço nunca vão para log; use `mascarar_telefone()` (RN-10).
- Todo cenário novo em `docs/bdd-r1.md` precisa de teste com `@pytest.mark.bdd("<ID>")`.

## Riscos aceitos

A integração com o WhatsApp é não oficial (Baileys). O WhatsApp pode bloquear o número e mudanças no protocolo podem parar o gateway até a biblioteca ser atualizada (RSK-01, RSK-02). Trocar pela API oficial é escrever outro adaptador da porta `CanalMensagens`.
