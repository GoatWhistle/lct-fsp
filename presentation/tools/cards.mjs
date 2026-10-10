import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { launch } from "./browser.mjs"

const [, , input, output] = process.argv
if (!input) {
  console.error("usage: npm run cards -- <cards.html> [out-dir]")
  process.exit(2)
}
const file = path.resolve(input)
const outDir = path.resolve(output ?? path.dirname(file))
fs.mkdirSync(outDir, { recursive: true })

const browser = await launch()
const page = await browser.newPage({ viewport: { width: 1200, height: 1400 }, deviceScaleFactor: 2 })
await page.goto(pathToFileURL(file).href)
await page.evaluate(() => document.fonts.ready)
const cards = page.locator("section.card[data-name]")
const count = await cards.count()
for (let i = 0; i < count; i += 1) {
  const name = await cards.nth(i).getAttribute("data-name")
  const target = path.join(outDir, `${name}.png`)
  await cards.nth(i).screenshot({ path: target })
  console.log(path.relative(process.cwd(), target))
}
await browser.close()
if (!count) {
  console.error('no <section class="card" data-name="..."> elements found')
  process.exit(1)
}
