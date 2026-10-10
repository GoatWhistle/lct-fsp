import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { chromium } from "playwright-core"
import { ROOT } from "./assemble.mjs"

export const DECK = path.join(ROOT, "dist", "deck.html")

export const launch = async () => {
  const executablePath = process.env.CHROME_PATH
  const options = executablePath ? { executablePath } : { channel: process.env.CHROME_CHANNEL || "chrome" }
  try {
    return await chromium.launch(options)
  } catch (error) {
    console.error("cannot start Chrome: set CHROME_PATH to a Chrome or Chromium binary, or install Google Chrome")
    console.error(String(error.message).split("\n")[0])
    process.exit(2)
  }
}

export const requireDeck = () => {
  if (!fs.existsSync(DECK)) {
    console.error("dist/deck.html not found, run npm run build first")
    process.exit(1)
  }
}

export const deckUrl = (query = "", hash = "") => `${pathToFileURL(DECK).href}${query}${hash}`

export const waitReady = (page) =>
  page.waitForFunction(() => document.documentElement.classList.contains("is-ready"), null, { timeout: 15000 })
