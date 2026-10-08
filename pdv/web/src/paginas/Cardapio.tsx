import { useCallback, useEffect, useState } from "react";

import { ErroApi, type Categoria, type Item } from "../api";
import { useSessao } from "../App";
import { brl, lerPreco } from "../formato";

export default function Cardapio() {
  const { api } = useSessao();
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [itens, setItens] = useState<Item[]>([]);
  const [erro, setErro] = useState("");
  const [novaCategoria, setNovaCategoria] = useState("");

  const carregar = useCallback(async () => {
    const [c, i] = await Promise.all([api<Categoria[]>("/categorias"), api<Item[]>("/itens")]);
    setCategorias(c);
    setItens(i);
  }, [api]);

  useEffect(() => {
    carregar().catch(() => setErro("Não foi possível carregar o cardápio."));
  }, [carregar]);

  async function acao(fn: () => Promise<unknown>) {
    setErro("");
    try {
      await fn();
      await carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível salvar.");
    }
  }

  function criarCategoria(e: React.FormEvent) {
    e.preventDefault();
    const ordem = categorias.length ? Math.max(...categorias.map((c) => c.ordem)) + 1 : 1;
    acao(() => api("/categorias", "POST", { nome: novaCategoria, ordem })).then(() => setNovaCategoria(""));
  }

  function mover(c: Categoria, delta: number) {
    const ordenadas = [...categorias];
    const i = ordenadas.findIndex((x) => x.id === c.id);
    const j = i + delta;
    if (j < 0 || j >= ordenadas.length) return;
    [ordenadas[i], ordenadas[j]] = [ordenadas[j], ordenadas[i]];
    acao(() =>
      Promise.all(ordenadas.map((x, n) => (x.ordem !== n + 1 ? api(`/categorias/${x.id}`, "PATCH", { ordem: n + 1 }) : null))),
    );
  }

  return (
    <section className="cardapio">
      <div className="pagina-topo">
        <h1>Cardápio</h1>
        <p className="ajuda">O robô mostra só categorias ativas e itens disponíveis, nesta ordem.</p>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      {categorias.length === 0 && (
        <p className="vazio">Comece criando uma categoria, como “Pratos” ou “Bebidas”. Depois adicione os itens nela.</p>
      )}

      {categorias.map((c, n) => (
        <article key={c.id} className={`categoria ${c.ativa ? "" : "inativa"}`}>
          <header className="categoria-cabeca">
            <h2>
              <span className="categoria-pos">{n + 1}</span> {c.nome}
            </h2>
            <div className="acoes">
              <button className="icone" aria-label={`Subir ${c.nome}`} onClick={() => mover(c, -1)} disabled={n === 0}>
                ↑
              </button>
              <button
                className="icone"
                aria-label={`Descer ${c.nome}`}
                onClick={() => mover(c, 1)}
                disabled={n === categorias.length - 1}
              >
                ↓
              </button>
              <label className="alternar">
                <input
                  type="checkbox"
                  checked={c.ativa}
                  onChange={() => acao(() => api(`/categorias/${c.id}`, "PATCH", { ativa: !c.ativa }))}
                />
                Ativa
              </label>
            </div>
          </header>
          <ul className="itens">
            {itens
              .filter((i) => i.categoria_id === c.id)
              .map((i) => (
                <LinhaItem key={i.id} item={i} aoSalvar={(campos) => acao(() => api(`/itens/${i.id}`, "PATCH", campos))} />
              ))}
          </ul>
          <NovoItem
            aoCriar={(nome, preco, descricao) =>
              acao(() =>
                api("/itens", "POST", {
                  categoria_id: c.id,
                  nome,
                  descricao,
                  preco_centavos: preco,
                  ordem: itens.filter((i) => i.categoria_id === c.id).length + 1,
                }),
              )
            }
          />
        </article>
      ))}

      <form className="nova-categoria" onSubmit={criarCategoria}>
        <label>
          Nova categoria
          <input value={novaCategoria} onChange={(e) => setNovaCategoria(e.target.value)} required maxLength={80} />
        </label>
        <button className="primario">Criar categoria</button>
      </form>
    </section>
  );
}

function LinhaItem({ item, aoSalvar }: { item: Item; aoSalvar: (campos: Partial<Item>) => Promise<void> }) {
  const [editando, setEditando] = useState(false);
  const [nome, setNome] = useState(item.nome);
  const [preco, setPreco] = useState((item.preco_centavos / 100).toFixed(2).replace(".", ","));
  const [descricao, setDescricao] = useState(item.descricao);
  const centavos = lerPreco(preco);

  if (editando) {
    return (
      <li className="item editando">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (centavos === null) return;
            aoSalvar({ nome, descricao, preco_centavos: centavos }).then(() => setEditando(false));
          }}
        >
          <input aria-label="Nome do item" value={nome} onChange={(e) => setNome(e.target.value)} required />
          <input aria-label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
          <input
            aria-label="Preço em reais"
            value={preco}
            onChange={(e) => setPreco(e.target.value)}
            aria-invalid={centavos === null}
            inputMode="decimal"
          />
          <button className="primario" disabled={centavos === null}>
            Salvar
          </button>
          <button type="button" className="link" onClick={() => setEditando(false)}>
            Desistir
          </button>
        </form>
      </li>
    );
  }
  return (
    <li className={`item ${item.disponivel ? "" : "indisponivel"}`}>
      <span className="item-nome">
        {item.nome}
        {item.descricao && <small>{item.descricao}</small>}
      </span>
      <span className="item-preco">{brl(item.preco_centavos)}</span>
      <label className="alternar">
        <input type="checkbox" checked={item.disponivel} onChange={() => aoSalvar({ disponivel: !item.disponivel })} />
        {item.disponivel ? "Disponível" : "Indisponível"}
      </label>
      <button className="link" onClick={() => setEditando(true)}>
        Editar
      </button>
    </li>
  );
}

function NovoItem({ aoCriar }: { aoCriar: (nome: string, preco: number, descricao: string) => Promise<void> }) {
  const [nome, setNome] = useState("");
  const [preco, setPreco] = useState("");
  const [descricao, setDescricao] = useState("");
  const centavos = lerPreco(preco);
  return (
    <form
      className="novo-item"
      onSubmit={(e) => {
        e.preventDefault();
        if (centavos === null) return;
        aoCriar(nome, centavos, descricao).then(() => {
          setNome("");
          setPreco("");
          setDescricao("");
        });
      }}
    >
      <input aria-label="Nome do novo item" placeholder="Novo item" value={nome} onChange={(e) => setNome(e.target.value)} required />
      <input aria-label="Descrição do novo item" placeholder="Descrição (opcional)" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
      <input
        aria-label="Preço do novo item em reais"
        placeholder="Preço, ex.: 45,90"
        value={preco}
        onChange={(e) => setPreco(e.target.value)}
        aria-invalid={preco !== "" && centavos === null}
        inputMode="decimal"
        required
      />
      <button disabled={centavos === null}>Adicionar item</button>
    </form>
  );
}
