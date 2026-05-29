import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": { target: proxyTarget, changeOrigin: true },
      "/health": { target: proxyTarget, changeOrigin: true },
      "/metrics": { target: proxyTarget, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts")) return "echarts";
          if (id.includes("node_modules/echarts-for-react")) return "echarts";
          if (id.includes("node_modules/react-router")) return "react";
          if (id.includes("node_modules/react") || id.includes("node_modules/react-dom")) return "react";
          if (id.includes("node_modules/lucide-react")) return "icons";
          if (id.includes("node_modules/i18next") || id.includes("react-i18next")) return "i18n";
          if (id.includes("/components/command/")) return "command";
          if (id.includes("/components/charts/")) return "charts-ui";
        }
      }
    },
    chunkSizeWarningLimit: 520
  }
});
