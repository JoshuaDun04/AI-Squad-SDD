import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Em desenvolvimento, /api vai para a API local (no app quem faz isso é o servidor do painel)
const proxy = { "/api": { target: "http://localhost:8000", rewrite: (p: string) => p.replace(/^\/api/, "") } };

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  test: { environment: "node" },
});
