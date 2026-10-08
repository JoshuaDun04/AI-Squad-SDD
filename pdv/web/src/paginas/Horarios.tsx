import { useEffect, useState } from "react";

import { ErroApi, type Horarios as HorariosApi } from "../api";
import { useSessao } from "../App";
import { DIAS } from "../formato";

interface Linha {
  aberto: boolean;
  abre: string;
  fecha: string;
}

export default function Horarios() {
  const { api } = useSessao();
  const [linhas, setLinhas] = useState<Linha[]>(DIAS.map(() => ({ aberto: false, abre: "11:00", fecha: "23:00" })));
  const [info, setInfo] = useState<HorariosApi | null>(null);
  const [erro, setErro] = useState("");
  const [salvo, setSalvo] = useState(false);

  async function carregar() {
    const h = await api<HorariosApi>("/horarios");
    setInfo(h);
    setLinhas(
      DIAS.map((_, d) => {
        const f = h.faixas.find((x) => x.dia_semana === d);
        return f ? { aberto: true, abre: f.abre, fecha: f.fecha } : { aberto: false, abre: "11:00", fecha: "23:00" };
      }),
    );
  }

  useEffect(() => {
    carregar().catch(() => setErro("Não foi possível carregar os horários."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const invalidos = linhas.map((l) => l.aberto && l.fecha <= l.abre);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setSalvo(false);
    try {
      await api(
        "/horarios",
        "PUT",
        linhas.flatMap((l, d) => (l.aberto ? [{ dia_semana: d, abre: l.abre, fecha: l.fecha }] : [])),
      );
      await carregar();
      setSalvo(true);
    } catch (err) {
      setErro(err instanceof ErroApi ? err.message : "Não foi possível salvar.");
    }
  }

  function mudar(d: number, campos: Partial<Linha>) {
    setSalvo(false);
    setLinhas((ls) => ls.map((l, i) => (i === d ? { ...l, ...campos } : l)));
  }

  return (
    <section className="horarios">
      <div className="pagina-topo">
        <h1>Horário de funcionamento</h1>
        {info && (
          <p className="ajuda">
            {info.aberto_agora ? "Aberto agora." : `Fechado agora. ${info.proxima_abertura}`} Fuso: {info.fuso}.
          </p>
        )}
      </div>
      <p className="ajuda">Fora destes horários o robô informa quando o restaurante abre e não aceita pedidos.</p>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <form onSubmit={salvar}>
        <table className="tabela horarios-tabela">
          <tbody>
            {linhas.map((l, d) => (
              <tr key={d} className={l.aberto ? "" : "fechado"}>
                <th scope="row">
                  <label className="alternar">
                    <input type="checkbox" checked={l.aberto} onChange={() => mudar(d, { aberto: !l.aberto })} />
                    {DIAS[d]}
                  </label>
                </th>
                <td>
                  {l.aberto ? (
                    <span className="faixa">
                      <input
                        type="time"
                        aria-label={`${DIAS[d]}: abre às`}
                        value={l.abre}
                        onChange={(e) => mudar(d, { abre: e.target.value })}
                        required
                      />
                      às
                      <input
                        type="time"
                        aria-label={`${DIAS[d]}: fecha às`}
                        value={l.fecha}
                        onChange={(e) => mudar(d, { fecha: e.target.value })}
                        aria-invalid={invalidos[d]}
                        required
                      />
                      {invalidos[d] && <small className="erro-campo">Fechamento precisa ser depois da abertura.</small>}
                    </span>
                  ) : (
                    <span className="fechado-texto">Fechado</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="rodape-form">
          <button className="primario" disabled={invalidos.some(Boolean)}>
            Salvar horários
          </button>
          {salvo && <span role="status">Horários salvos.</span>}
        </div>
      </form>
    </section>
  );
}
