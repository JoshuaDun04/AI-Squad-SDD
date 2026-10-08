/**
 * Converte uma mensagem do Baileys no evento que a API espera.
 * Só transporte: nenhuma regra de negócio aqui (ADR-0002).
 */

export interface ChaveMensagem {
  id?: string | null;
  remoteJid?: string | null;
  remoteJidAlt?: string | null;
  fromMe?: boolean | null;
}

export interface MensagemBaileys {
  key: ChaveMensagem;
  pushName?: string | null;
  message?: {
    conversation?: string | null;
    extendedTextMessage?: { text?: string | null } | null;
    buttonsResponseMessage?: { selectedDisplayText?: string | null } | null;
    listResponseMessage?: { title?: string | null } | null;
  } | null;
}

export interface MensagemNormalizada {
  mensagemId: string;
  /** Só dígitos: número de telefone (ou identificador LID quando o WhatsApp esconde o número). */
  telefone: string;
  /** JID para responder a esse contato. */
  jidResposta: string;
  nomePerfil: string;
  texto: string;
}

const SUFIXO_PN = "@s.whatsapp.net";
const SUFIXO_LID = "@lid";

function usuario(jid: string): string {
  return jid.split("@")[0].split(":")[0];
}

function ehPn(jid?: string | null): jid is string {
  return !!jid && jid.endsWith(SUFIXO_PN);
}

function ehLid(jid?: string | null): jid is string {
  return !!jid && jid.endsWith(SUFIXO_LID);
}

export function extrairTexto(m: MensagemBaileys["message"]): string {
  if (!m) return "";
  return (
    m.conversation ??
    m.extendedTextMessage?.text ??
    m.buttonsResponseMessage?.selectedDisplayText ??
    m.listResponseMessage?.title ??
    ""
  ).trim();
}

/** Retorna null para o que o robô não deve tratar: grupos, status, canais, mensagens nossas. */
export function normalizar(msg: MensagemBaileys): MensagemNormalizada | null {
  const { key } = msg;
  if (!key?.id || key.fromMe) return null;
  const remoto = key.remoteJid ?? "";
  let jidPn: string | null = null;
  if (ehPn(remoto)) jidPn = remoto;
  else if (ehPn(key.remoteJidAlt)) jidPn = key.remoteJidAlt;

  let jidResposta: string;
  let telefone: string;
  if (jidPn) {
    telefone = usuario(jidPn);
    jidResposta = `${telefone}${SUFIXO_PN}`;
  } else if (ehLid(remoto)) {
    telefone = usuario(remoto);
    jidResposta = `${telefone}${SUFIXO_LID}`;
  } else {
    return null; // grupo, broadcast, newsletter...
  }
  if (!/^\d{8,15}$/.test(telefone)) return null;
  return {
    mensagemId: key.id,
    telefone,
    jidResposta,
    nomePerfil: (msg.pushName ?? "").slice(0, 120),
    texto: extrairTexto(msg.message).slice(0, 2000),
  };
}

/** Mascara para logs (RN-10): "*****-4567". */
export function mascarar(telefone: string): string {
  const d = telefone.replace(/\D/g, "");
  return d.length >= 4 ? `*****-${d.slice(-4)}` : "*****";
}

/** Telefone com DDD, com país ou LID: 10 a 15 dígitos sem encostar em letra, dígito ou hífen. */
const RE_NUMERO = /(?<![\w-])\+?\d{10,15}(?![\w-])/g;

/**
 * Mascara números de telefone em qualquer valor que vá para o log do Baileys (REV-09).
 * A biblioteca registra chaves de mensagem e JIDs em avisos comuns.
 */
export function mascararProfundo(valor: unknown, profundidade = 0): unknown {
  if (typeof valor === "string") return valor.replace(RE_NUMERO, (m) => mascarar(m));
  if (profundidade > 6 || valor === null || typeof valor !== "object") return valor;
  if (valor instanceof Error) {
    return { tipo: valor.name, mensagem: mascararProfundo(valor.message, profundidade + 1) };
  }
  if (Array.isArray(valor)) return valor.map((v) => mascararProfundo(v, profundidade + 1));
  if (Buffer.isBuffer(valor) || valor instanceof Uint8Array) return `<${valor.length} bytes>`;
  const saida: Record<string, unknown> = {};
  for (const [chave, v] of Object.entries(valor)) saida[chave] = mascararProfundo(v, profundidade + 1);
  return saida;
}
