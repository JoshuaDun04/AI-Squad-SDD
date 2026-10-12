"use strict";
/** Endereço do computador na rede local e escolha de portas livres (RF-23). */
const net = require("node:net");
const os = require("node:os");

const VIRTUAL = /virtual|vmware|vbox|docker|wsl|hyper-v|vethernet|loopback|tailscale|zerotier|hamachi/i;

function privado(ip) {
  if (ip.startsWith("10.") || ip.startsWith("192.168.")) return true;
  const m = /^172\.(\d+)\./.exec(ip);
  return m !== null && Number(m[1]) >= 16 && Number(m[1]) <= 31;
}

/** IPv4 privado de uma placa física; Wi-Fi e Ethernet antes de adaptadores virtuais. */
function enderecoLocal(interfaces = os.networkInterfaces()) {
  const candidatos = [];
  for (const [nome, lista] of Object.entries(interfaces)) {
    for (const i of lista || []) {
      if (i.internal || (i.family !== "IPv4" && i.family !== 4) || !privado(i.address)) continue;
      candidatos.push({ nome, ip: i.address, virtual: VIRTUAL.test(nome) });
    }
  }
  candidatos.sort((a, b) => Number(a.virtual) - Number(b.virtual) || (a.ip.startsWith("192.168.") ? -1 : 1));
  return candidatos.length ? candidatos[0].ip : null;
}

function portaDisponivel(porta, host) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once("error", () => resolve(false));
    s.listen(porta, host, () => s.close(() => resolve(true)));
  });
}

/** A preferida, ou a próxima livre até +10; 0 escolhe qualquer porta livre. */
async function escolherPorta(preferida, host = "127.0.0.1") {
  if (preferida === 0) {
    return new Promise((resolve, reject) => {
      const s = net.createServer();
      s.once("error", reject);
      s.listen(0, host, () => {
        const { port } = s.address();
        s.close(() => resolve(port));
      });
    });
  }
  for (let p = preferida; p <= preferida + 10; p++) {
    if (await portaDisponivel(p, host)) return p;
  }
  throw new Error(`nenhuma porta livre entre ${preferida} e ${preferida + 10}`);
}

module.exports = { enderecoLocal, escolherPorta, privado };
