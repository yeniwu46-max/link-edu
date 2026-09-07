import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    port: 5188,
    strictPort: true,
    proxy: {
      "/api": {
        target:
          loadEnv(mode, process.cwd(), "LINK_").LINK_BACKEND_URL ||
          "http://127.0.0.1:5000",
        ws: true,
      },
    },
  },
}));
