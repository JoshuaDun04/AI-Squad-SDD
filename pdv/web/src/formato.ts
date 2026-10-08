/** Formatação na borda (ADR-0004): o resto do sistema só conhece centavos. */

export function brl(centavos: number): string {
  const sinal = centavos < 0 ? "-" : "";
  const abs = Math.abs(centavos);
  const reais = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sinal}R$ ${reais},${String(abs % 100).padStart(2, "0")}`;
}

/** "45,90" | "45.90" | "45" → 4590. Retorna null se inválido ou ≤ 0. */
export function lerPreco(texto: string): number | null {
  const limpo = texto.trim().replace(/^R\$\s*/i, "");
  const m = /^(\d{1,6})(?:[.,](\d{1,2}))?$/.exec(limpo);
  if (!m) return null;
  const cent = m[2] ? Number(m[2].padEnd(2, "0")) : 0;
  const valor = Number(m[1]) * 100 + cent;
  return valor > 0 ? valor : null;
}

export function minutosDesde(iso: string, agora: number): number {
  return Math.max(0, Math.floor((agora - new Date(iso).getTime()) / 60_000));
}

/** Urgência do ticket na cozinha: tempo desde a confirmação. */
export function urgencia(minutos: number): "normal" | "atencao" | "atrasado" {
  if (minutos >= 25) return "atrasado";
  if (minutos >= 15) return "atencao";
  return "normal";
}

export function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export const PAGAMENTO: Record<string, string> = { pix: "Pix", dinheiro: "Dinheiro", cartao: "Cartão" };

export const DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

/** Próximo status permitido (RN-09) e o rótulo do botão que leva até ele. */
export const PROXIMO: Record<string, { status: string; acao: string } | undefined> = {
  Recebido: { status: "Em preparo", acao: "Começar preparo" },
  "Em preparo": { status: "Pronto", acao: "Marcar pronto" },
  Pronto: { status: "Finalizado", acao: "Entregue" },
};
