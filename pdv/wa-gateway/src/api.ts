/** Cliente do webhook da API (gateway → API), com novas tentativas. */

export type EventoApi =
  | {
      tipo: "mensagem";
      restaurante_id: string;
      mensagem_id: string;
      telefone: string;
      nome_perfil: string;
      texto: string;
      recebida_em: string;
    }
  | {
      tipo: "status_conexao";
      restaurante_id: string;
      status: "aguardando_qr" | "conectado" | "desconectado";
      qr_code?: string;
    };

export interface ClienteApi {
  enviarEvento(evento: EventoApi): Promise<boolean>;
}

export class ClienteApiHttp implements ClienteApi {
  constructor(
    private readonly apiUrl: string,
    private readonly token: string,
    private readonly tentativas = 4,
    private readonly esperaBaseMs = 500,
    private readonly log: (msg: string) => void = (m) => console.warn(m),
  ) {}

  /**
   * A API deduplica por mensagem_id (BDD-WA-04), então repetir é seguro.
   * 4xx (exceto 429) não é repetido: o evento é inválido.
   */
  async enviarEvento(evento: EventoApi): Promise<boolean> {
    for (let i = 0; i < this.tentativas; i++) {
      try {
        const resp = await fetch(`${this.apiUrl}/canal/webhook`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Gateway-Token": this.token },
          body: JSON.stringify(evento),
          signal: AbortSignal.timeout(10_000),
        });
        if (resp.ok) return true;
        if (resp.status < 500 && resp.status !== 429) {
          this.log(`webhook recusado status=${resp.status} tipo=${evento.tipo}`);
          return false;
        }
        this.log(`webhook falhou status=${resp.status} tentativa=${i + 1}`);
      } catch (erro) {
        this.log(`webhook inacessível tentativa=${i + 1} erro=${(erro as Error).name}`);
      }
      await new Promise((r) => setTimeout(r, this.esperaBaseMs * 2 ** i));
    }
    return false;
  }
}
