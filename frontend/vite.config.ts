import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    outDir: "../app/static/react",
    emptyOutDir: true,
    minify: "esbuild",
    rollupOptions: {
      input: {
        management: resolve(__dirname, "src/management/main.tsx"),
        ranges: resolve(__dirname, "src/ranges/main.tsx"),
        library: resolve(__dirname, "src/library/main.tsx"),
        hosts: resolve(__dirname, "src/hosts/main.tsx"),
        "host-detail": resolve(__dirname, "src/host-detail/main.tsx"),
      },
      output: {
        entryFileNames: "[name]/[name].js",
        chunkFileNames: "shared/[name]-[hash].js",
        assetFileNames: "shared/[name]-[hash][extname]",
      },
    },
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify(
      mode === "test" ? "test" : "production",
    ),
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
}));
