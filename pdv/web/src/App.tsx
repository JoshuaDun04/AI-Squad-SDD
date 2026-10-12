import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  chamar,
  definirAoExpirar,
  salvarSessao,
  sessaoSalva,
  type Eu,
  type Papel,
  type Sessao,
} from "./api";
import Cardapio from "./paginas/Cardapio";
import Cozinha from "./paginas/Cozinha";
import Entrar from "./paginas/Entrar";
import Equipe from "./paginas/Equipe";
import Horarios from "./paginas/Horarios";
import Pedidos from "./paginas/Pedidos";
import Relatorio from "./paginas/Relatorio";
import Whatsapp from "./paginas/Whatsapp";

interface Contexto {
  sessao: Sessao;
  eu: Eu | null;
  api: <T>(caminho: string, metodo?: string, corpo?: unknown) => Promise<T>;
}

const Ctx = createContext<Contexto | null>(null);

export function useSessao(): Contexto {
  const c = useContext(Ctx);
  if (!c) throw new Error("fora da sessão");
  return c;
}

interface Pagina {
  rota: string;
  nome: string;
  papeis: Papel[];
  Componente: () => React.JSX.Element;
}

const PAGINAS: Pagina[] = [
  { rota: "cozinha", nome: "Cozinha", papeis: ["admin", "atendente", "cozinha"], Componente: Cozinha },
  { rota: "pedidos", nome: "Pedidos do dia", papeis: ["admin", "atendente"], Componente: Pedidos },
  { rota: "cardapio", nome: "Cardápio", papeis: ["admin"], Componente: Cardapio },
  { rota: "horarios", nome: "Horários", papeis: ["admin"], Componente: Horarios },
  { rota: "whatsapp", nome: "WhatsApp", papeis: ["admin"], Componente: Whatsapp },
  { rota: "equipe", nome: "Equipe", papeis: ["admin"], Componente: Equipe },
  { rota: "relatorio", nome: "Relatório", papeis: ["admin"], Componente: Relatorio },
];

function rotaAtual(): string {
  return window.location.hash.replace(/^#\/?/, "") || "cozinha";
}

export default function App() {
  const [sessao, setSessao] = useState<Sessao | null>(sessaoSalva);
  const [eu, setEu] = useState<Eu | null>(null);
  const [rota, setRota] = useState(rotaAtual);

  const sair = useCallback(() => {
    salvarSessao(null);
    setSessao(null);
    setEu(null);
  }, []);

  useEffect(() => {
    definirAoExpirar(sair);
    const aoMudar = () => setRota(rotaAtual());
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, [sair]);

  const api = useCallback(
    <T,>(caminho: string, metodo?: string, corpo?: unknown) =>
      chamar<T>(caminho, { metodo, corpo, token: sessao?.token }),
    [sessao],
  );

  useEffect(() => {
    if (!sessao) return;
    api<Eu>("/auth/eu")
      .then((dados) => {
        setEu(dados);
        // O papel pode ter mudado desde o login: a interface segue o que a API diz agora
        if (dados.papel !== sessao.papel) {
          const atualizada = { ...sessao, papel: dados.papel };
          salvarSessao(atualizada);
          setSessao(atualizada);
        }
      })
      .catch(() => {});
  }, [sessao, api]);

  const ctx = useMemo(() => (sessao ? { sessao, eu, api } : null), [sessao, eu, api]);

  if (!sessao || !ctx) {
    return (
      <Entrar
        aoEntrar={(s) => {
          salvarSessao(s);
          setSessao(s);
          window.location.hash = s.papel === "cozinha" ? "#/cozinha" : "#/pedidos";
        }}
      />
    );
  }

  const permitidas = PAGINAS.filter((p) => p.papeis.includes(sessao.papel));
  const pagina = permitidas.find((p) => p.rota === rota) ?? permitidas[0];

  return (
    <Ctx.Provider value={ctx}>
      <div className={`casca ${pagina.rota === "cozinha" ? "casca-cozinha" : ""}`}>
        <header className="barra">
          <div className="marca">
            <span className="marca-nome">{eu?.restaurante_nome ?? " "}</span>
            <span className="marca-papel">{eu ? `${eu.email} · ${sessao.papel}` : ""}</span>
          </div>
          {permitidas.length > 1 && (
          <nav aria-label="Seções">
            {permitidas.map((p) => (
              <a key={p.rota} href={`#/${p.rota}`} aria-current={p.rota === pagina.rota ? "page" : undefined}>
                {p.nome}
              </a>
            ))}
          </nav>
          )}
          <button className="sair" onClick={sair}>
            Sair
          </button>
        </header>
        <main className="conteudo">
          <pagina.Componente />
        </main>
      </div>
    </Ctx.Provider>
  );
}
