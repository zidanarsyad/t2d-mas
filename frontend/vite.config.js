import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes("node_modules/recharts")) return "charts";
    if (id.includes("node_modules/lucide-react")) return "icons";
    if (id.includes("node_modules/react")) return "react-vendor";
  } } } },
  // The dashboard calls /api/*; Vite forwards it to the FastAPI backend.
  server: { proxy: { "/api": {
    target: process.env.VITE_API_TARGET || "http://localhost:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  } } },
});
