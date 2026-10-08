import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@fontsource-variable/archivo/wdth.css";

import App from "./App";
import "./estilo.css";

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
