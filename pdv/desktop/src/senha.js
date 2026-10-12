"use strict";
// Formulário de "Redefinir senha do dono" (RF-28). Fala com o app só por window.pdv (senha-preload.js).
(() => {
  const form = document.getElementById("form");
  const msg = document.getElementById("mensagem");
  const salvar = document.getElementById("salvar");
  const campos = ["email", "senha", "repetir"].map((id) => document.getElementById(id));

  function mostrar(texto, tipo) {
    msg.textContent = texto;
    msg.className = tipo;
  }

  document.getElementById("cancelar").addEventListener("click", () => window.close());

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const [email, senha, repetir] = campos.map((c) => c.value);
    if (senha !== repetir) return mostrar("As duas senhas não são iguais.", "erro");
    salvar.disabled = true;
    mostrar("Salvando…", "");
    const r = await window.pdv.redefinirSenha(email, senha);
    salvar.disabled = false;
    if (r.ok) {
      campos.forEach((c) => (c.value = ""));
      mostrar("Senha trocada. Entre no painel com a senha nova.", "ok");
      setTimeout(() => window.close(), 2500);
    } else {
      mostrar(r.erro, "erro");
    }
  });
})();
