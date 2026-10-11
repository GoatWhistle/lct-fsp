import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "e2e",
  testMatch: ["defense.spec.ts", "defense-vacancy.spec.ts"],
  timeout: 300_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  outputDir: "../docs/demo/recording",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3100",
    channel: "chrome",
    locale: "ru-RU",
    viewport: { width: 1440, height: 900 },
    video: { mode: "on", size: { width: 1440, height: 900 } },
    launchOptions: { slowMo: 700 },
  },
})
