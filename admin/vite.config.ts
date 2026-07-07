import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const apiPort = rootEnv.API_PORT || "8800";
  const adminPort = parseInt(rootEnv.ADMIN_PORT || "5180", 10);

  return {
    plugins: [react()],
    server: {
      port: adminPort,
      host: true,
      proxy: {
        "/api": { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true },
      },
    },
  };
});
