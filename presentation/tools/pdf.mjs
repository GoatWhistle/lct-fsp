import path from "node:path"
import { ROOT } from "./assemble.mjs"
import { deckUrl, launch, requireDeck, waitReady } from "./browser.mjs"

requireDeck()
const out = path.join(ROOT, "dist", "deck.pdf")
const browser = await launch()
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
const errors = []
page.on("pageerror", (error) => errors.push(error.message))
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text())
})
await page.goto(deckUrl("?print"))
await waitReady(page)
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(300)
const pages = await page.evaluate(() => document.querySelectorAll(".slide").length)
await page.pdf({ path: out, width: "1920px", height: "1080px", printBackground: true, preferCSSPageSize: true })
await browser.close()
if (errors.length) {
  console.error(`page errors:\n${[...new Set(errors)].join("\n")}`)
  process.exit(1)
}
console.log(`${path.relative(ROOT, out)} ${pages} pages`)
