import { describe, expect, it } from "vitest";

import { traduzirErro } from "./api";
import { brl, lerPreco, minutosDesde, PROXIMO, urgencia } from "./formato";

describe("formato", () => {
  it("formata centavos em reais", () => {
    expect(brl(4590)).toBe("R$ 45,90");
    expect(brl(10070)).toBe("R$ 100,70");
    expect(brl(123456)).toBe("R$ 1.234,56");
    expect(brl(5)).toBe("R$ 0,05");
  });

  it("lê preço digitado sem ponto flutuante", () => {
    expect(lerPreco("45,90")).toBe(4590);
    expect(lerPreco("45.9")).toBe(4590);
    expect(lerPreco("R$ 12")).toBe(1200);
    expect(lerPreco("0")).toBeNull();
    expect(lerPreco("-5")).toBeNull();
    expect(lerPreco("abc")).toBeNull();
    expect(lerPreco("1,234")).toBeNull();
  });

  it("calcula urgência do ticket", () => {
    const agora = Date.parse("2026-10-06T16:30:00Z");
    expect(minutosDesde("2026-10-06T16:10:00Z", agora)).toBe(20);
    expect(urgencia(14)).toBe("normal");
    expect(urgencia(15)).toBe("atencao");
    expect(urgencia(25)).toBe("atrasado");
  });

  it("só oferece o próximo passo da ordem de status", () => {
    expect(PROXIMO.Recebido?.status).toBe("Em preparo");
    expect(PROXIMO["Em preparo"]?.status).toBe("Pronto");
    expect(PROXIMO.Pronto?.status).toBe("Finalizado");
    expect(PROXIMO.Finalizado).toBeUndefined();
  });

  it("traduz erros da API para o usuário", () => {
    expect(traduzirErro(429, { erro: "muitas_tentativas" })).toMatch(/15 minutos/);
    expect(traduzirErro(403, {})).toMatch(/não permite/);
    expect(traduzirErro(422, { detalhe: "preco_centavos: inválido" })).toBe("preco_centavos: inválido");
  });
});
