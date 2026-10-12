import { useCallback, useEffect, useState } from "react";

import { ErroApi, type Relatorio as Dados, type ResumoTempo } from "../api";
import { useSessao } from "../App";
import { brl } from "../formato";

const PERIODOS = [1, 7, 14, 30];

function minutos(t: ResumoTempo): string {
  if (t.mediana_min === null) return "sem dados";
  return `${t.mediana_min.toLocaleString("pt-BR")} min`;
}

function dia(iso: string): string {
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

export default function Relatorio() {
  const { api } = useSessao();
  const [dias, setDias] = useState(7);
  const [dados, setDados] = useState<Dados | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    setErro("");
    try {
      setDados(await api<Dados>(`/relatorio?dias=${dias}`));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível carregar o relatório.");
    }
  }, [api, dias]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  return (
    <section className="relatorio">
      <div className="pagina-topo">
        <h1>Relatório</h1>
        <div className="periodos" role="group" aria-label="Período">
          {PERIODOS.map((p) => (
            <button key={p} className={p === dias ? "primario" : ""} aria-pressed={p === dias} onClick={() => setDias(p)}>
              {p === 1 ? "Hoje" : `${p} dias`}
            </button>
          ))}
        </div>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {dados && dados.totais.pedidos === 0 && (
        <p className="vazio">Nenhum pedido no período. Os números aparecem aqui conforme os pedidos chegam pelo WhatsApp.</p>
      )}
      {dados && dados.totais.pedidos > 0 && (
        <>
          <dl className="indicadores">
            <div>
              <dt>Pedidos</dt>
              <dd>{dados.totais.pedidos}</dd>
            </div>
            <div>
              <dt>Vendido</dt>
              <dd>{brl(dados.totais.vendido_centavos)}</dd>
            </div>
            <div>
              <dt>Ticket médio</dt>
              <dd>{dados.totais.ticket_medio_centavos === null ? "—" : brl(dados.totais.ticket_medio_centavos)}</dd>
            </div>
            <div>
              <dt>Até começar o preparo</dt>
              <dd>{minutos(dados.tempos.ate_preparo)}</dd>
            </div>
            <div>
              <dt>Tempo de preparo</dt>
              <dd>{minutos(dados.tempos.preparo)}</dd>
            </div>
            <div>
              <dt>Cancelados</dt>
              <dd>{dados.totais.cancelados}</dd>
            </div>
          </dl>
          <p className="ajuda">Tempos são a mediana: metade dos pedidos foi mais rápida que isso.</p>

          <h2>Por dia</h2>
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Dia</th>
                <th scope="col" className="num">Pedidos</th>
                <th scope="col" className="num">Finalizados</th>
                <th scope="col" className="num">Cancelados</th>
                <th scope="col" className="num">Entregas</th>
                <th scope="col" className="num">Vendido</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_dia.map((d) => (
                <tr key={d.dia}>
                  <td>{dia(d.dia)}</td>
                  <td className="num">{d.pedidos}</td>
                  <td className="num">{d.finalizados}</td>
                  <td className="num">{d.cancelados}</td>
                  <td className="num">{d.entregas}</td>
                  <td className="num">{brl(d.vendido_centavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="relatorio-colunas">
            <div>
              <h2>Horário dos pedidos</h2>
              <ul className="barras">
                {dados.por_hora.map((h) => {
                  const maior = Math.max(...dados.por_hora.map((x) => x.pedidos));
                  return (
                    <li key={h.hora}>
                      <span className="barras-rotulo">{String(h.hora).padStart(2, "0")}h</span>
                      <span className="barras-barra" style={{ width: `${(h.pedidos / maior) * 100}%` }} />
                      <span className="num">{h.pedidos}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
            <div>
              <h2>Mais pedidos</h2>
              <ol className="lista-simples">
                {dados.itens_mais_pedidos.map((i) => (
                  <li key={i.nome}>
                    {i.nome} <span className="num">{i.unidades} un.</span>
                  </li>
                ))}
              </ol>
              {dados.cancelamentos.length > 0 && (
                <>
                  <h2>Motivos de cancelamento</h2>
                  <ul className="lista-simples">
                    {dados.cancelamentos.map((c) => (
                      <li key={c.motivo}>
                        {c.motivo} <span className="num">{c.vezes}×</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
