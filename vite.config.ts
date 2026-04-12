import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 700,
  },
  server: {
    port: 5173,
    host: true,
  },
  optimizeDeps: {
    entries: ["index.html"],
    exclude: ["gradio"],
  },
});
