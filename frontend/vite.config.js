import { Agent } from "node:http";
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
    // 127.0.0.1, not localhost: uvicorn listens on IPv4 only, but Node tries localhost over IPv6
    // first, where another program (such as a Docker port proxy) may answer for port 8000.
    target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
    // A fresh connection per request: Node 19+ reuses idle sockets by default, but uvicorn
    // closes them after 5 s, and reusing a closed one fails the request with a 500.
    agent: new Agent({ keepAlive: false }),
  } } },
});
