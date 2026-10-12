"use strict";
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("pdv", {
  redefinirSenha: (email, senha) => ipcRenderer.invoke("redefinir-senha", String(email), String(senha)),
});
