export const TOKEN_MIN = 16;

export interface Config {
  porta: number;
  /** Só a própria máquina por padrão: a API e o app falam com o gateway em 127.0.0.1 (RT-18). */
  host: string;
  token: string;
  apiUrl: string;
  dataDir: string;
}

export class ConfigInvalida extends Error {}

/** Recusa iniciar sem GATEWAY_TOKEN forte (SEC-03). */
export function lerConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const token = env.GATEWAY_TOKEN ?? "";
  if (token.length < TOKEN_MIN) {
    throw new ConfigInvalida(`GATEWAY_TOKEN precisa ter pelo menos ${TOKEN_MIN} caracteres`);
  }
  const apiUrl = (env.API_URL ?? "http://api:8000").replace(/\/+$/, "");
  return {
    porta: Number(env.PORT ?? 3001),
    host: env.HOST ?? "127.0.0.1",
    token,
    apiUrl,
    dataDir: env.DATA_DIR ?? "/data",
  };
}
