import { useCallback, useEffect, useState } from "react";

import { ErroApi, type PedidoFila, type StatusPedido } from "../api";
import { useSessao } from "../App";
import { hora, minutosDesde, PROXIMO, urgencia } from "../formato";

const INTERVALO_MS = 3000; // RT-05: polling de 3 s, critério de até 5 s

const COLUNAS: { status: StatusPedido; titulo: string; vazio: string }[] = [
  { status: "Recebido", titulo: "Novos", vazio: "Nenhum pedido novo." },
  { status: "Em preparo", titulo: "Em preparo", vazio: "Nada no fogo agora." },
  { status: "Pronto", titulo: "Prontos", vazio: "Nenhum pedido esperando retirada ou entrega." },
];

export default function Cozinha() {
  const { api, sessao, eu } = useSessao();
  const [fila, setFila] = useState<PedidoFila[] | null>(null);
  const [agora, setAgora] = useState(Date.now());
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setFila(await api<PedidoFila[]>("/fila"));
      setOffline(false);
    } catch {
      setOffline(true);
    }
    setAgora(Date.now());
  }, [api]);

  useEffect(() => {
    carregar();
    const t = window.setInterval(carregar, INTERVALO_MS);
    return () => window.clearInterval(t);
  }, [carregar]);

  async function avancar(p: PedidoFila) {
    const prox = PROXIMO[p.status];
    if (!prox) return;
    setOcupado(p.pedido_id);
    setAviso("");
    try {
      await api(`/pedidos/${p.pedido_id}/status`, "POST", { novo_status: prox.status });
    } catch (e) {
      setAviso(e instanceof ErroApi ? e.message : "Não foi possível mudar o status.");
    } finally {
      setOcupado(null);
      carregar();
    }
  }

  // Cozinha não finaliza (entrega ao cliente é com o atendente), mas pode, pelo contrato.
  const podeFinalizar = sessao.papel !== "cozinha";

  return (
    <section className="cozinha" aria-labelledby="titulo-cozinha">
      <div className="cozinha-topo">
        <h1 id="titulo-cozinha">Fila da cozinha</h1>
        <p className={offline ? "estado offline" : "estado"} role="status">
          {offline ? "Sem conexão. Tentando de novo…" : fila ? `${fila.length} na fila` : "Carregando…"}
        </p>
      </div>
      {aviso && (
        <p className="erro" role="alert">
          {aviso}
        </p>
      )}
      <div className="colunas">
        {COLUNAS.map((col) => {
          const pedidos = (fila ?? []).filter((p) => p.status === col.status);
          return (
            <div className="coluna" key={col.status} data-status={col.status}>
              <h2>
                {col.titulo} <span className="contagem">{pedidos.length}</span>
              </h2>
              {fila && pedidos.length === 0 && <p className="vazio">{col.vazio}</p>}
              <ol className="tickets">
                {pedidos.map((p) => {
                  const min = minutosDesde(p.criado_em, agora);
                  const prox = PROXIMO[p.status];
                  const mostrarBotao = prox && (prox.status !== "Finalizado" || podeFinalizar);
                  return (
                    <li key={p.pedido_id} className={`ticket ${urgencia(min)}`}>
                      <div className="ticket-cabeca">
                        <span className="ticket-num">#{p.numero}</span>
                        <span className="ticket-tempo">
                          <time dateTime={p.criado_em}>{hora(p.criado_em, eu?.fuso)}</time>
                          <strong>{min} min</strong>
                        </span>
                      </div>
                      <p className="ticket-tipo">{p.tipo === "entrega" ? "Entrega" : "Retirada"}</p>
                      <ul className="ticket-itens">
                        {p.itens.map((i, n) => (
                          <li key={n}>
                            <b>{i.quantidade}×</b> {i.nome}
                          </li>
                        ))}
                      </ul>
                      {p.observacao && <p className="ticket-obs">{p.observacao}</p>}
                      {mostrarBotao && (
                        <button
                          className="ticket-acao"
                          disabled={ocupado === p.pedido_id}
                          onClick={() => avancar(p)}
                        >
                          {prox.acao}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ol>
            </div>
          );
        })}
      </div>
    </section>
  );
}
