import { useCallback, useEffect, useState } from "react";

import { ErroApi, type StatusWhatsapp } from "../api";
import { useSessao } from "../App";

const TEXTO: Record<StatusWhatsapp["status"], string> = {
  desconectado: "Desconectado",
  aguardando_qr: "Aguardando leitura do QR code",
  conectado: "Conectado",
};

export default function Whatsapp() {
  const { api } = useSessao();
  const [st, setSt] = useState<StatusWhatsapp | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setSt(await api<StatusWhatsapp>("/whatsapp/status"));
    } catch {
      /* mantém o último estado */
    }
  }, [api]);

  useEffect(() => {
    carregar();
    const t = window.setInterval(carregar, 2000);
    return () => window.clearInterval(t);
  }, [carregar]);

  async function executar(caminho: string) {
    setErro("");
    setOcupado(true);
    try {
      await api(caminho, "POST");
      await carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível falar com o WhatsApp.");
    } finally {
      setOcupado(false);
    }
  }

  const status = st?.status ?? "desconectado";

  return (
    <section className="whatsapp">
      <div className="pagina-topo">
        <h1>Conexão com o WhatsApp</h1>
        <p className="estado-whatsapp" data-status={status} role="status">
          {TEXTO[status]}
        </p>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      {status === "desconectado" && (
        <div className="passos">
          <p>Conecte o número do restaurante para o robô começar a responder os clientes.</p>
          <button className="primario" disabled={ocupado} onClick={() => executar("/whatsapp/conectar")}>
            Gerar QR code
          </button>
        </div>
      )}

      {status === "aguardando_qr" && (
        <div className="qr-bloco">
          {st?.qr_code_data_url ? (
            <img src={st.qr_code_data_url} alt="QR code para conectar o WhatsApp" width={280} height={280} />
          ) : (
            <p className="qr-espera">Gerando o QR code…</p>
          )}
          <ol className="instrucoes">
            <li>No celular do restaurante, abra o WhatsApp.</li>
            <li>Toque em Configurações e depois em Aparelhos conectados.</li>
            <li>Toque em Conectar um aparelho e aponte a câmera para este código.</li>
          </ol>
        </div>
      )}

      {status === "conectado" && (
        <div className="passos">
          <p>O robô está atendendo. Para trocar de número, desconecte e gere um novo QR code.</p>
          <button className="perigo" disabled={ocupado} onClick={() => executar("/whatsapp/desconectar")}>
            Desconectar número
          </button>
        </div>
      )}

      <p className="aviso-risco">
        Esta conexão usa uma integração não oficial com o WhatsApp. Use um número dedicado ao restaurante: o WhatsApp pode
        bloquear números que enviam muitas mensagens automáticas.
      </p>
    </section>
  );
}
