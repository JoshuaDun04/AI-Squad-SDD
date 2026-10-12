/** App Windows (RT-19): se o app morrer, a entrada padrão fecha e o gateway sai junto. */
export function vigiarProcessoPai(
  entrada: NodeJS.ReadableStream = process.stdin,
  sair: (codigo: number) => void = (codigo) => process.exit(codigo),
): void {
  entrada.on("data", () => {});
  entrada.on("end", () => sair(0));
  entrada.on("error", () => sair(0));
}
