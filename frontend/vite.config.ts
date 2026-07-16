import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    outDir: "../app/static/react/management",
    emptyOutDir: true,
    minify: "esbuild",
    lib: {
      entry: resolve(__dirname, "src/management/main.tsx"),
      formats: ["es"],
      fileName: () => "management.js",
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
