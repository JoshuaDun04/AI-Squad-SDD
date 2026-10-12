import { useCallback, useEffect, useState } from "react";

import { ErroApi, type Papel, type Usuario } from "../api";
import { useSessao } from "../App";
import EnderecoCozinha from "./EnderecoCozinha";

const PAPEIS: { valor: Papel; nome: string; descricao: string }[] = [
  { valor: "cozinha", nome: "Cozinha", descricao: "vê a fila e avança o preparo" },
  { valor: "atendente", nome: "Atendente", descricao: "vê pedidos, endereço e pode cancelar" },
  { valor: "admin", nome: "Admin", descricao: "tudo, inclusive cardápio, horários e equipe" },
];

export default function Equipe() {
  const { api, eu } = useSessao();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [papel, setPapel] = useState<Papel>("cozinha");
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => setUsuarios(await api<Usuario[]>("/usuarios")), [api]);

  useEffect(() => {
    carregar().catch(() => setErro("Não foi possível carregar a equipe."));
  }, [carregar]);

  async function acao(fn: () => Promise<unknown>) {
    setErro("");
    try {
      await fn();
      await carregar();
      return true;
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível salvar.");
      return false;
    }
  }

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    if (await acao(() => api("/usuarios", "POST", { email, senha, papel }))) {
      setEmail("");
      setSenha("");
    }
  }

  return (
    <section className="equipe">
      <div className="pagina-topo">
        <h1>Equipe</h1>
      </div>
      <EnderecoCozinha />
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">E-mail</th>
            <th scope="col">Acesso</th>
            <th scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.id} className={u.ativo ? "" : "inativo"}>
              <td>{u.email}</td>
              <td>{PAPEIS.find((p) => p.valor === u.papel)?.nome}</td>
              <td>
                {u.id === eu?.usuario_id ? (
                  "Você"
                ) : (
                  <button className="link" onClick={() => acao(() => api(`/usuarios/${u.id}`, "PATCH", { ativo: !u.ativo }))}>
                    {u.ativo ? "Desativar acesso" : "Reativar acesso"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="novo-usuario" onSubmit={criar}>
        <h2>Dar acesso a alguém</h2>
        <label>
          E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Senha inicial
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required minLength={8} autoComplete="new-password" />
        </label>
        <fieldset>
          <legend>Acesso</legend>
          {PAPEIS.map((p) => (
            <label key={p.valor} className="opcao">
              <input type="radio" name="papel" checked={papel === p.valor} onChange={() => setPapel(p.valor)} />
              <b>{p.nome}</b> <span>{p.descricao}</span>
            </label>
          ))}
        </fieldset>
        <button className="primario">Dar acesso</button>
      </form>
    </section>
  );
}
