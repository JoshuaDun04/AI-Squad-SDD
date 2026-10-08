import { useCallback, useEffect, useState } from "react";

import { ErroApi, type PedidoDetalhe, type PedidoFila } from "../api";
import { useSessao } from "../App";
import { brl, hora, PAGAMENTO } from "../formato";

function hoje(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function Pedidos() {
  const { api } = useSessao();
  const [data, setData] = useState(hoje);
  const [lista, setLista] = useState<PedidoFila[] | null>(null);
  const [aberto, setAberto] = useState<PedidoDetalhe | null>(null);
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    try {
      setLista(await api<PedidoFila[]>(`/pedidos?data=${data}`));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível carregar os pedidos.");
    }
  }, [api, data]);

  useEffect(() => {
    carregar();
    const t = window.setInterval(carregar, 10_000);
    return () => window.clearInterval(t);
  }, [carregar]);

  async function abrir(id: string) {
    setErro("");
    setMotivo("");
    try {
      setAberto(await api<PedidoDetalhe>(`/pedidos/${id}`));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível abrir o pedido.");
    }
  }

  async function cancelar(e: React.FormEvent) {
    e.preventDefault();
    if (!aberto) return;
    setErro("");
    try {
      await api(`/pedidos/${aberto.pedido_id}/cancelar`, "POST", { motivo });
      await abrir(aberto.pedido_id);
      carregar();
    } catch (err) {
      setErro(err instanceof ErroApi ? err.message : "Não foi possível cancelar.");
    }
  }

  const cancelavel = aberto && (aberto.status === "Recebido" || aberto.status === "Em preparo");

  return (
    <section className="pedidos">
      <div className="pagina-topo">
        <h1>Pedidos do dia</h1>
        <label className="campo-inline">
          Data
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
        </label>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <div className="pedidos-grade">
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Nº</th>
              <th scope="col">Hora</th>
              <th scope="col">Tipo</th>
              <th scope="col">Status</th>
              <th scope="col" className="num">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {lista?.length === 0 && (
              <tr>
                <td colSpan={5} className="vazio">
                  Nenhum pedido nesta data. Os pedidos aparecem aqui assim que o cliente confirma no WhatsApp.
                </td>
              </tr>
            )}
            {lista?.map((p) => (
              <tr
                key={p.pedido_id}
                className={aberto?.pedido_id === p.pedido_id ? "selecionado" : ""}
                onClick={() => abrir(p.pedido_id)}
              >
                <td>
                  <button className="link" onClick={() => abrir(p.pedido_id)}>
                    #{p.numero}
                  </button>
                </td>
                <td>{hora(p.criado_em)}</td>
                <td>{p.tipo === "entrega" ? "Entrega" : "Retirada"}</td>
                <td>
                  <span className="selo" data-status={p.status}>
                    {p.status}
                  </span>
                </td>
                <td className="num">{p.total_centavos !== undefined ? brl(p.total_centavos) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {aberto && (
          <aside className="detalhe" aria-label={`Pedido ${aberto.numero}`}>
            <div className="detalhe-cabeca">
              <h2>Pedido #{aberto.numero}</h2>
              <button className="link" onClick={() => setAberto(null)}>
                Fechar
              </button>
            </div>
            <span className="selo" data-status={aberto.status}>
              {aberto.status}
            </span>
            <dl>
              <dt>Cliente</dt>
              <dd>
                {aberto.cliente?.nome_perfil || "Sem nome"} · {aberto.cliente?.telefone}
              </dd>
              <dt>{aberto.tipo === "entrega" ? "Entregar em" : "Tipo"}</dt>
              <dd>{aberto.tipo === "entrega" ? aberto.endereco : "Retirada no local"}</dd>
              <dt>Pagamento</dt>
              <dd>
                {PAGAMENTO[aberto.pagamento]}
                {aberto.pagamento === "dinheiro" &&
                  (aberto.troco_para_centavos ? `, troco para ${brl(aberto.troco_para_centavos)}` : ", sem troco")}
              </dd>
              {aberto.observacao && (
                <>
                  <dt>Observação do cliente</dt>
                  <dd>{aberto.observacao}</dd>
                </>
              )}
              {aberto.motivo_cancelamento && (
                <>
                  <dt>Motivo do cancelamento</dt>
                  <dd>{aberto.motivo_cancelamento}</dd>
                </>
              )}
            </dl>
            <table className="tabela compacta">
              <tbody>
                {aberto.itens.map((i) => (
                  <tr key={i.item_id + i.nome}>
                    <td>
                      {i.quantidade} × {i.nome}
                    </td>
                    <td className="num">{brl(i.preco_unitario_centavos * i.quantidade)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td className="num">
                    <b>{brl(aberto.total_centavos)}</b>
                  </td>
                </tr>
              </tfoot>
            </table>
            {cancelavel && (
              <form onSubmit={cancelar} className="cancelar">
                <label>
                  Motivo do cancelamento
                  <input
                    value={motivo}
                    onChange={(e) => setMotivo(e.target.value)}
                    required
                    minLength={3}
                    maxLength={300}
                    placeholder="O cliente recebe este texto no WhatsApp"
                  />
                </label>
                <button className="perigo">Cancelar pedido</button>
              </form>
            )}
          </aside>
        )}
      </div>
    </section>
  );
}
