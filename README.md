# PDV Restaurantes

Pedidos pelo WhatsApp entrando direto na fila da cozinha, num aplicativo que o dono do restaurante instala no próprio computador com Windows.

O cliente conversa com um robô de menu numerado (categorias → itens → quantidade → carrinho → retirada ou entrega → pagamento → confirmação). O pedido aparece na tela da cozinha em poucos segundos, e cada mudança de status avisa o cliente no WhatsApp.

## Para o dono do restaurante

Baixe o instalador em [Releases](https://github.com/JoshuaDun04/AI-Squad-SDD/releases/latest) e siga o [guia de instalação](docs/operacao/instalacao-windows.md). O app abre com o Windows, fica perto do relógio, faz backup todo dia e se atualiza sozinho. A tela da cozinha é qualquer tablet ou TV com navegador no mesmo Wi-Fi.

## O que tem aqui

```
docs/                 governança SDD: RTM, cenários BDD, contratos, ADRs, decisões, parecer do Gate 4
  desktop/            RTM e cenários do app Windows (DEC-11)
  operacao/           guia de instalação e plano do piloto
CONTEXT.md            glossário do domínio
pdv/
  api/                Python · FastAPI · SQLAlchemy · SQLite (PostgreSQL também funciona) — todas as regras de negócio
  wa-gateway/         TypeScript · Baileys — só transporte do WhatsApp (sessão, QR, mensagens)
  web/                React · TypeScript — painel do admin, do atendente e da cozinha
  desktop/            Electron — instala, sobe e supervisiona as peças acima no Windows (ADR-0011)
  e2e/                Playwright: cadastro → cardápio → pedido → cozinha → cancelamento
```

Como o app funciona no computador do restaurante:

```
Electron (bandeja, janela, backups, atualização)
 ├─ servidor do painel  0.0.0.0:8080   painel + /api → API   (tablet da cozinha entra por aqui)
 ├─ API (Python 3.12 embutido)  127.0.0.1:<livre>   banco SQLite em %APPDATA%\PDV Restaurantes
 └─ robô do WhatsApp (Node do Electron)  127.0.0.1:<livre>
```

## Desenvolver

```bash
# API
cd pdv/api
pip install --require-hashes -r requirements.lock.txt && pip install pytest pytest-cov
python -m pytest                                   # SQLite em memória
TEST_DATABASE_URL=postgresql+psycopg://pdv:pdv@localhost/pdv_test python -m pytest   # PostgreSQL
python scripts/verificar_rtm.py                    # cobertura BDD (R1 + app) + regras de isolamento

# Gateway e painel (precisam estar construídos para o app)
cd pdv/wa-gateway && npm ci && npm test && npm run build
cd pdv/web && npm ci && npm test && npm run build  # `npm run dev` para desenvolver com proxy de /api

# App (no Linux ou Windows, com Python 3.12 e as dependências da API instaladas)
cd pdv/desktop && npm ci
npm test                                           # supervisor, servidor do painel e integração com API e robô reais
npm start                                          # abre o app em modo desenvolvimento
node scripts/rodar-servicos.mjs --dados /tmp/pdv   # só os serviços, sem Electron (CI e e2e)
```

Toda mudança de modelo precisa de migração nova: `alembic revision --autogenerate -m "..."` e depois `alembic check`. Mudou dependência da API? Regere os dois locks (`requirements.lock.txt` e `requirements-windows.lock.txt`; o comando está no topo de cada um). O CI confere que eles batem.

## Gerar uma versão

1. Suba a versão em `pdv/desktop/package.json` (ex.: `1.0.1`) e faça commit.
2. Crie a tag: `git tag v1.0.1 && git push origin v1.0.1`.
3. O job `windows` do CI monta o instalador, instala num Windows limpo, roda o e2e no app instalado e publica em Releases. Os apps instalados baixam a versão nova em até 6 horas.

O instalador não tem assinatura de código: o Windows mostra um aviso na primeira instalação (RSK-05).

## Regras que valem para qualquer mudança

- Nenhuma rota consulta o banco direto; só repositórios que recebem `restaurante_id` (ADR-0001). O verificador falha se isso for quebrado.
- Dinheiro é sempre `int` em centavos (ADR-0004).
- Regra de negócio fica na API, nunca no gateway (ADR-0002).
- Telefone e endereço nunca vão para log; use `mascarar_telefone()` (RN-10).
- Todo cenário novo em `docs/bdd-r1.md` ou `docs/desktop/bdd-desktop.md` precisa de teste com `@pytest.mark.bdd("<ID>")` (API) ou com o ID no título (app).
- API e robô só ouvem em `127.0.0.1`; só o servidor do painel fica na rede local, e ele nunca repassa `/api/canal/*` (RT-18).

## Riscos aceitos

A integração com o WhatsApp é não oficial (Baileys). O WhatsApp pode bloquear o número e mudanças no protocolo podem parar o gateway até a biblioteca ser atualizada (RSK-01, RSK-02). Trocar pela API oficial é escrever outro adaptador da porta `CanalMensagens`. Os riscos do app Windows (painel por HTTP na rede local, backups no mesmo disco, instalador sem assinatura, computador desligado, rede marcada como Pública) estão em [docs/desktop/RTM-desktop.md](docs/desktop/RTM-desktop.md).
