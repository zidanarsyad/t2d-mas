import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes("node_modules/recharts")) return "charts";
    if (id.includes("node_modules/lucide-react")) return "icons";
    if (id.includes("node_modules/react")) return "react-vendor";
  } } } },
  server: { proxy: { "/api": {
    target: process.env.VITE_API_TARGET || "http://localhost:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  } } },
});
