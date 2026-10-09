import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"
import { htmlMeta } from "./scripts/htmlMeta.ts"

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000"
const sourceRoot = fileURLToPath(new URL("./src", import.meta.url))
const localesDir = fileURLToPath(new URL("./src/shared/i18n/locales", import.meta.url))

export default defineConfig({
  plugins: [react(), htmlMeta(localesDir)],
  resolve: { alias: { "@": sourceRoot } },
  server: {
    port: 3000,
    proxy: { "/api": { target: backendUrl, changeOrigin: true } },
  },
  test: {
    css: { modules: { classNameStrategy: "non-scoped" } },
    projects: [
      {
        extends: true,
        test: { name: "node", environment: "node", include: ["tests/**/*.test.ts"] },
      },
      {
        extends: true,
        test: {
          name: "dom",
          environment: "jsdom",
          include: ["tests/**/*.test.tsx"],
          setupFiles: ["tests/setup/polyfills.ts", "tests/setup/dom.ts"],
        },
      },
    ],
  },
})
