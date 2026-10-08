import { useState } from "react";

import { chamar, ErroApi, type Sessao } from "../api";

export default function Entrar({ aoEntrar }: { aoEntrar: (s: Sessao) => void }) {
  const [modo, setModo] = useState<"entrar" | "cadastrar">("entrar");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      if (modo === "cadastrar") {
        await chamar("/restaurantes", {
          metodo: "POST",
          corpo: { nome, admin_email: email, admin_senha: senha },
        });
      }
      const s = await chamar<Sessao>("/auth/login", { metodo: "POST", corpo: { email, senha } });
      aoEntrar(s);
    } catch (err) {
      setErro(err instanceof ErroApi ? err.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="entrada">
      <div className="entrada-lado" aria-hidden="true">
        <p className="entrada-ticket">
          <span className="entrada-num">#1</span>
          <span>2 × Tambaqui assado</span>
          <span>1 × Suco de cupuaçu</span>
        </p>
        <p className="entrada-legenda">Pedidos do WhatsApp direto na cozinha.</p>
      </div>
      <form className="entrada-form" onSubmit={enviar}>
        <h1>{modo === "entrar" ? "Entrar no painel" : "Cadastrar restaurante"}</h1>
        {modo === "cadastrar" && (
          <label>
            Nome do restaurante
            <input value={nome} onChange={(e) => setNome(e.target.value)} required minLength={2} maxLength={120} />
          </label>
        )}
        <label>
          E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            minLength={modo === "cadastrar" ? 8 : 1}
            autoComplete={modo === "entrar" ? "current-password" : "new-password"}
          />
          {modo === "cadastrar" && <small>Pelo menos 8 caracteres.</small>}
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button className="primario" disabled={enviando}>
          {modo === "entrar" ? "Entrar" : "Cadastrar e entrar"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setModo(modo === "entrar" ? "cadastrar" : "entrar");
            setErro("");
          }}
        >
          {modo === "entrar" ? "Primeiro acesso? Cadastre seu restaurante" : "Já tenho conta"}
        </button>
      </form>
    </div>
  );
}
