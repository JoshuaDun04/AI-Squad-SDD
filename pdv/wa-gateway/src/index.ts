import { ClienteApiHttp } from "./api.js";
import { criarApp } from "./app.js";
import { ConfigInvalida, lerConfig } from "./config.js";
import { SessoesBaileys } from "./sessoes.js";

async function main(): Promise<void> {
  let config;
  try {
    config = lerConfig();
  } catch (erro) {
    if (erro instanceof ConfigInvalida) {
      console.error(erro.message);
      process.exit(1);
    }
    throw erro;
  }
  const api = new ClienteApiHttp(config.apiUrl, config.token);
  const sessoes = new SessoesBaileys(config.dataDir, api);
  const app = criarApp(sessoes, config.token);
  app.listen(config.porta, () => console.info(`wa-gateway ouvindo na porta ${config.porta}`));
  await sessoes.restaurar();
}

main().catch((erro) => {
  console.error(`falha ao iniciar: ${(erro as Error).message}`);
  process.exit(1);
});
