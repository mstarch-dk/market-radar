import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `pnpm dev` serves on 5173 and forwards /api to `radar serve` (8780); `pnpm build` writes dist/ for radar serve.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8780" } },
  build: { outDir: "dist", emptyOutDir: true },
});
