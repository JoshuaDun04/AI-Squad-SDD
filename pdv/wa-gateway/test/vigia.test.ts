import assert from "node:assert/strict";
import { PassThrough } from "node:stream";
import { it } from "node:test";

import { vigiarProcessoPai } from "../src/vigia.js";

it("sai quando a entrada padrão do app fecha (RT-19)", async () => {
  const entrada = new PassThrough();
  const codigos: number[] = [];
  vigiarProcessoPai(entrada, (c) => codigos.push(c));
  entrada.write("qualquer coisa");
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(codigos, []);
  entrada.end();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(codigos, [0]);
});
