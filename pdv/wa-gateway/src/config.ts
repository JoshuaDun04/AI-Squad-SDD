export const TOKEN_MIN = 16;

export interface Config {
  porta: number;
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
    token,
    apiUrl,
    dataDir: env.DATA_DIR ?? "/data",
  };
}
