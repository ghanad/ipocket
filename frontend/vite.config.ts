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
        login: resolve(__dirname, "src/login/main.tsx"),
        management: resolve(__dirname, "src/management/main.tsx"),
        ranges: resolve(__dirname, "src/ranges/main.tsx"),
        "range-addresses": resolve(
          __dirname,
          "src/range-addresses/main.tsx",
        ),
        library: resolve(__dirname, "src/library/main.tsx"),
        hosts: resolve(__dirname, "src/hosts/main.tsx"),
        "host-detail": resolve(__dirname, "src/host-detail/main.tsx"),
        "ip-assets": resolve(__dirname, "src/ip-assets/main.tsx"),
        "ip-asset-detail": resolve(__dirname, "src/ip-asset-detail/main.tsx"),
        "audit-log": resolve(__dirname, "src/audit-log/main.tsx"),
        users: resolve(__dirname, "src/users/main.tsx"),
        "account-password": resolve(
          __dirname,
          "src/account-password/main.tsx",
        ),
        "data-ops": resolve(__dirname, "src/data-ops/main.tsx"),
        connectors: resolve(__dirname, "src/connectors/main.tsx"),
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
