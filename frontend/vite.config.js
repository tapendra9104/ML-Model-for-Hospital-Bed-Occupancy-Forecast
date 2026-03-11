import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function packageName(id) {
  const source = id.split("node_modules/")[1];
  if (!source) {
    return null;
  }
  const parts = source.split("/");
  if (parts[0].startsWith("@")) {
    return `${parts[0]}/${parts[1]}`;
  }
  return parts[0];
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000"
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }
          const name = packageName(id);
          if (!name) {
            return undefined;
          }
          if (["react", "react-dom", "scheduler"].includes(name)) {
            return "vendor-react";
          }
          if (
            ["recharts", "recharts-scale", "victory-vendor", "lodash", "prop-types"].includes(name) ||
            name.startsWith("d3-")
          ) {
            return "vendor-charts";
          }
          return undefined;
        }
      }
    }
  }
});
