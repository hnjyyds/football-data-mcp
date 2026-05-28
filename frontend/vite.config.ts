import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8910";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8920,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true
      }
    }
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ["recharts"]
        }
      }
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testSetup.ts"],
    globals: false
  }
});
