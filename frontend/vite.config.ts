import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    // Em Codespaces o polling evita que o watcher perca eventos no volume montado.
    watch: { usePolling: true },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        // three.js pesa; separá-lo mantém o bundle inicial do dashboard leve.
        manualChunks: {
          three: ["three", "@react-three/fiber", "@react-three/drei"],
          charts: ["recharts"],
          // O mapa só é baixado quando o painel troca para ele; em chunk
          // próprio isso continua valendo depois do build.
          map: ["leaflet", "react-leaflet"],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
