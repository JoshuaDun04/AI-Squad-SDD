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

Requisitos: Ubuntu 24.04 ou Debian 12 com Docker, 2 GB de RAM, portas 80 e 443 abertas, e um número de WhatsApp dedicado ao restaurante. Domínio próprio é opcional: `<ip-com-hífens>.sslip.io` funciona com HTTPS.

```bash
cd pdv
./deploy/pdv.sh instalar        # pergunta o domínio, gera o .env, sobe tudo com HTTPS (Caddy)
./deploy/pdv.sh verificar       # serviços, HTTPS, webhook fechado, WhatsApp, logs sem telefone, disco
```

O passo a passo completo, com firewall, backup diário e alerta no celular, está em [docs/operacao/implantacao-vps.md](docs/operacao/implantacao-vps.md). O plano do piloto com um restaurante está em [docs/operacao/plano-piloto.md](docs/operacao/plano-piloto.md).

Outros comandos: `atualizar`, `backup`, `restaurar`, `relatorio [dias]`, `logs [serviço]`.

Sem o kit de produção (só para testar numa rede local): `cp .env.example .env`, troque os segredos e rode `docker compose up -d --build`; o painel fica em `http://<ip>:8080`, sem HTTPS.

## Desenvolver

```bash
# API
cd pdv/api
pip install --require-hashes -r requirements.lock.txt && pip install pytest pytest-cov
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
