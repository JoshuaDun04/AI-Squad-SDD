---
status: accepted
---
# Aplicativo desktop Windows com Electron, Python embutido e gateway no Node do Electron

O produto passa a ser instalado no computador do restaurante (DEC-11). O instalador NSIS, gerado pelo electron-builder, coloca um aplicativo Electron que:

- inicia a API (Python 3.12 **embutido**, distribuição oficial "embeddable" com as dependências do lock) e o gateway do WhatsApp (o mesmo código TypeScript, executado pelo próprio Node do Electron com `ELECTRON_RUN_AS_NODE`) como processos filhos, ouvindo só em `127.0.0.1`;
- serve o painel por um servidor HTTP em Node, na porta 8080 da rede local, com os mesmos cabeçalhos de segurança do nginx anterior e o mesmo bloqueio de `/api/canal/*`;
- supervisiona os processos (reinicia com espera crescente), mostra ícone na bandeja, abre com o Windows, impede a suspensão do processo, faz backup diário e verifica atualizações no GitHub Releases (electron-updater).

## Considered Options

- **Docker Desktop no computador do restaurante:** reaproveita o compose, mas exige virtualização, instalação pesada e conhecimento técnico do dono.
- **Reescrever a API em Node:** um runtime só, mas joga fora a API testada (314 testes, mutação 98%).
- **PyInstaller para a API:** um executável, mas antivírus costumam acusar falso positivo em binários do PyInstaller; o Python embutido é a distribuição oficial e roda os mesmos arquivos `.py` testados.
- **Tauri em vez de Electron:** instalador menor, mas o gateway precisa de Node de qualquer forma; o Electron já traz o Node.
- **Electron + Python embutido (escolhido).**

## Consequences

- O instalador fica na casa de 150 a 200 MB.
- O build do instalador roda num runner Windows do CI; a montagem e o teste de fumaça acontecem lá.
- Dados em `%APPDATA%\PDV Restaurantes`: banco, sessões do WhatsApp, backups, logs e o arquivo de segredos gerado na primeira execução.
- A regra de negócio continua só na API (ADR-0002); o Electron não conhece pedidos.
- Python embutido: o `python312._pth` manda no `sys.path` (a variável `PYTHONPATH` é ignorada), por isso o preparo dos recursos escreve nele `Lib\site-packages` e `..\api`. As dependências vêm de um lock próprio para Windows (`requirements-windows.lock.txt`), porque o `pip --platform` avalia marcadores de ambiente pela máquina que monta, não pela de destino.
- A API e o robô recebem a entrada padrão ligada ao app e saem quando ela fecha: se o Electron cair, não sobra processo segurando o banco SQLite.
- Firewall: o instalador cria uma regra de entrada só para rede privada, pedindo administrador uma vez (instalação por usuário, sem elevação nas atualizações). O app avisa quando a rede está como Pública.
