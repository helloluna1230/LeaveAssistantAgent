import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_AGENT_ENDPOINT points at the hosted agent (default local host).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/responses": {
        target: process.env.VITE_AGENT_ENDPOINT || "http://localhost:8088",
        changeOrigin: true,
      },
      "/demo": {
        target: process.env.VITE_AGENT_ENDPOINT || "http://localhost:8088",
        changeOrigin: true,
      },
    },
  },
});
