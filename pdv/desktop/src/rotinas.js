"use strict";
/**
 * Decisões do app sem dependência do Electron (testáveis com Node puro).
 */

const DIA_MS = 24 * 60 * 60 * 1000;

/** Backup diário (RN-25): nenhum backup ainda, ou o último tem mais de 24 h. */
function precisaBackup(ultimo, agora = new Date()) {
  if (!ultimo) return true;
  return agora.getTime() - ultimo.getTime() >= DIA_MS;
}

/**
 * Compara dois retratos de /canal/conexoes e devolve os avisos a mostrar (RF-26).
 * Só avisa em mudança: caiu (era "conectado" e deixou de ser) ou voltou.
 * Retrato vazio (API fora do ar) não gera aviso; o supervisor cuida disso.
 */
function avisosWhatsapp(anterior, atual) {
  if (!atual.length) return [];
  const antes = new Map(anterior.map((c) => [c.restaurante, c.status]));
  const avisos = [];
  for (const { restaurante, status } of atual) {
    const era = antes.get(restaurante);
    if (era === "conectado" && status !== "conectado") {
      avisos.push({
        tipo: "caiu",
        titulo: "WhatsApp desconectado",
        texto: `${restaurante}: o robô parou de receber pedidos. Abra o painel e conecte o WhatsApp de novo.`,
      });
    } else if (era !== undefined && era !== "conectado" && status === "conectado") {
      avisos.push({ tipo: "voltou", titulo: "WhatsApp conectado", texto: `${restaurante}: o robô voltou a receber pedidos.` });
    }
  }
  return avisos;
}

/** Texto curto do estado de um serviço para o menu da bandeja. */
const ROTULOS = {
  api: "Sistema",
  whatsapp: "WhatsApp (robô)",
};
const ESTADOS = {
  parado: "parado",
  iniciando: "iniciando…",
  rodando: "funcionando",
  reiniciando: "reiniciando…",
  falhou: "PARADO — precisa de atenção",
};
function rotuloServico(servico, estado) {
  return `${ROTULOS[servico] || servico}: ${ESTADOS[estado] || estado}`;
}

/**
 * Saída de `Get-NetConnectionProfile | ForEach-Object NetworkCategory` (uma por linha).
 * A regra do firewall só vale para rede privada: se alguma conexão está como Pública,
 * o tablet da cozinha não consegue abrir o painel.
 */
function redePublica(saida) {
  return String(saida || "")
    .split(/\r?\n/)
    .map((l) => l.trim().toLowerCase())
    .some((l) => l === "public" || l === "0");
}

module.exports = { precisaBackup, avisosWhatsapp, rotuloServico, redePublica, DIA_MS };
