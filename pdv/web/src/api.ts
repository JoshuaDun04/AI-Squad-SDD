/** Cliente da API. Todas as rotas passam por /api (servidor do painel no app, ou proxy do Vite). */

export type Papel = "admin" | "atendente" | "cozinha";
export type StatusPedido = "Recebido" | "Em preparo" | "Pronto" | "Finalizado" | "Cancelado";

export interface Sessao {
  token: string;
  papel: Papel;
  restaurante_id: string;
}

export interface Eu {
  usuario_id: string;
  email: string;
  papel: Papel;
  restaurante_id: string;
  restaurante_nome: string;
  fuso: string;
  hoje: string;
}

export interface Categoria {
  id: string;
  nome: string;
  ordem: number;
  ativa: boolean;
}

export interface Item {
  id: string;
  categoria_id: string;
  nome: string;
  descricao: string;
  preco_centavos: number;
  disponivel: boolean;
  ordem: number;
}

export interface Faixa {
  dia_semana: number;
  abre: string;
  fecha: string;
}

export interface Horarios {
  fuso: string;
  aberto_agora: boolean;
  proxima_abertura: string;
  faixas: Faixa[];
}

export interface PedidoFila {
  pedido_id: string;
  numero: number;
  status: StatusPedido;
  criado_em: string;
  tipo: "retirada" | "entrega";
  observacao: string | null;
  itens: { nome: string; quantidade: number }[];
  total_centavos?: number;
  pagamento?: string;
}

export interface PedidoDetalhe {
  pedido_id: string;
  numero: number;
  data_local: string;
  status: StatusPedido;
  tipo: "retirada" | "entrega";
  endereco: string | null;
  pagamento: "pix" | "dinheiro" | "cartao";
  troco_para_centavos: number | null;
  total_centavos: number;
  motivo_cancelamento: string | null;
  observacao: string | null;
  criado_em: string;
  cliente: { nome_perfil: string; telefone: string } | null;
  itens: { item_id: string; nome: string; preco_unitario_centavos: number; quantidade: number }[];
}

export interface Instalacao {
  modo: "local" | "servidor";
  cadastro_aberto: boolean;
  endereco_rede: string | null;
}

export interface ResumoTempo {
  pedidos: number;
  mediana_min: number | null;
  p90_min: number | null;
}

export interface Relatorio {
  dias: number;
  ate: string;
  whatsapp: string;
  totais: { pedidos: number; cancelados: number; vendido_centavos: number; ticket_medio_centavos: number | null };
  por_dia: {
    dia: string;
    pedidos: number;
    finalizados: number;
    cancelados: number;
    em_aberto: number;
    entregas: number;
    ticket_medio_centavos: number | null;
    vendido_centavos: number;
  }[];
  tempos: { ate_preparo: ResumoTempo; preparo: ResumoTempo; pronto_ate_finalizado: ResumoTempo };
  por_hora: { hora: number; pedidos: number }[];
  cancelamentos: { motivo: string; vezes: number }[];
  itens_mais_pedidos: { nome: string; unidades: number }[];
}

export interface Usuario {
  id: string;
  email: string;
  papel: Papel;
  ativo: boolean;
}

export interface StatusWhatsapp {
  status: "desconectado" | "aguardando_qr" | "conectado";
  qr_code_data_url?: string;
  atualizado_em?: string;
}

export class ErroApi extends Error {
  constructor(
    public readonly status: number,
    public readonly codigo: string,
    detalhe: string,
  ) {
    super(detalhe);
  }
}

const CHAVE = "pdv.sessao";

export function sessaoSalva(): Sessao | null {
  try {
    const bruto = localStorage.getItem(CHAVE);
    return bruto ? (JSON.parse(bruto) as Sessao) : null;
  } catch {
    return null;
  }
}

export function salvarSessao(s: Sessao | null): void {
  try {
    if (s) localStorage.setItem(CHAVE, JSON.stringify(s));
    else localStorage.removeItem(CHAVE);
  } catch {
    /* navegador sem storage: a sessão vale só nesta aba */
  }
}

type AoExpirar = () => void;
let aoExpirar: AoExpirar = () => {};
export function definirAoExpirar(fn: AoExpirar): void {
  aoExpirar = fn;
}

export async function chamar<T>(
  caminho: string,
  opcoes: { metodo?: string; corpo?: unknown; token?: string | null } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (opcoes.corpo !== undefined) headers["Content-Type"] = "application/json";
  if (opcoes.token) headers.Authorization = `Bearer ${opcoes.token}`;
  let resp: Response;
  try {
    resp = await fetch(`/api${caminho}`, {
      method: opcoes.metodo ?? "GET",
      headers,
      body: opcoes.corpo !== undefined ? JSON.stringify(opcoes.corpo) : undefined,
    });
  } catch {
    throw new ErroApi(0, "sem_conexao", "Sem conexão com o servidor. Verifique a internet.");
  }
  if (resp.status === 204) return undefined as T;
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401 && opcoes.token) aoExpirar();
    throw new ErroApi(resp.status, dados.erro ?? "erro", traduzirErro(resp.status, dados));
  }
  return dados as T;
}

export function traduzirErro(status: number, dados: { erro?: string; detalhe?: string }): string {
  switch (dados.erro) {
    case "muitas_tentativas":
      return "Muitas tentativas de entrada. Espere 15 minutos e tente de novo.";
    case "nao_autenticado":
      return "E-mail ou senha incorretos.";
    case "restaurante_ja_cadastrado":
      return "Este computador já tem um restaurante cadastrado. Entre com o e-mail do dono.";
    case "email_em_uso":
      return "Esse e-mail já está cadastrado.";
    case "transicao_invalida":
      return "O pedido já mudou de status. A lista foi atualizada.";
    case "gateway_indisponivel":
      return "O serviço de WhatsApp não respondeu. Tente de novo em instantes.";
    case "categoria_com_itens":
      return "A categoria ainda tem itens. Mova os itens ou desative a categoria.";
  }
  if (status === 403) return "Seu acesso não permite essa ação.";
  if (status === 404) return "Não encontrado. Pode ter sido removido.";
  return dados.detalhe || "Algo deu errado. Tente de novo.";
}
