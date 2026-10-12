import { useEffect, useState } from "react";

import { chamar, type Instalacao } from "../api";

/** Endereço do painel na rede local, para abrir no tablet ou TV da cozinha (RF-23). */
export default function EnderecoCozinha() {
  const [endereco, setEndereco] = useState<string | null>(null);

  useEffect(() => {
    chamar<Instalacao>("/instalacao")
      .then((i) => setEndereco(i.endereco_rede))
      .catch(() => {});
  }, []);

  if (!endereco) return null;
  return (
    <p className="endereco-cozinha">
      Tela da cozinha: no tablet ou TV conectado ao mesmo Wi-Fi, abra <strong>{endereco}</strong> e entre com o
      usuário da cozinha.
    </p>
  );
}
