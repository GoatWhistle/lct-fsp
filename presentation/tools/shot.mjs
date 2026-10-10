import fs from "node:fs"
import path from "node:path"
import { parseArgs } from "node:util"
import { ROOT } from "./assemble.mjs"
import { deckUrl, launch, requireDeck, waitReady } from "./browser.mjs"

const { values } = parseArgs({
  options: {
    slide: { type: "string" },
    at: { type: "string" },
    out: { type: "string", default: "shots" },
    width: { type: "string", default: "1920" },
    height: { type: "string", default: "1080" },
  },
})

const pad = (value) => String(value).padStart(2, "0")
const times = values.at ? values.at.split(",").map(Number) : null
const outDir = path.resolve(ROOT, values.out)

requireDeck()
fs.mkdirSync(outDir, { recursive: true })
const browser = await launch()
const page = await browser.newPage({ viewport: { width: Number(values.width), height: Number(values.height) } })
const errors = []
page.on("pageerror", (error) => errors.push(error.message))
page.on("console", (message) => {
  if (message.type() === "error" || message.type() === "warning") errors.push(message.text())
})
await page.goto(deckUrl(times ? "" : "?static", "#1"))
await waitReady(page)
await page.evaluate(() => document.fonts.ready)

const slides = await page.evaluate(() => window.deck.slides)
const picks = values.slide
  ? values.slide.split(",").map((wanted) => {
      const index = slides.findIndex((slide, i) => slide.id === wanted || String(i + 1) === wanted)
      if (index < 0) {
        console.error(`slide ${wanted} not found`)
        process.exit(1)
      }
      return index
    })
  : slides.map((_, index) => index)

const layout = (index) =>
  page.evaluate((i) => {
    const slide = document.querySelectorAll(".slide")[i]
    const stage = document.querySelector(".stage").getBoundingClientRect()
    const issues = []
    for (const node of slide.querySelectorAll("*")) {
      if (node.closest("svg") && node.tagName.toLowerCase() !== "svg") continue
      const style = getComputedStyle(node)
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) continue
      const box = node.getBoundingClientRect()
      if (!box.width || !box.height) continue
      const cls = typeof node.className === "string" && node.className.trim() ? `.${node.className.trim().split(/\s+/).join(".")}` : ""
      const name = `${node.tagName.toLowerCase()}${cls}`
      if (box.left < stage.left - 1 || box.top < stage.top - 1 || box.right > stage.right + 1 || box.bottom > stage.bottom + 1) {
        issues.push(`outside the stage: ${name}`)
      }
      if (!node.children.length && node.scrollWidth > node.clientWidth + 2 && node.clientWidth > 0 && style.overflowX === "visible") {
        issues.push(`text overflows its box: ${name}`)
      }
    }
    return [...new Set(issues)]
  }, index)

const report = []
for (const index of picks) {
  const slide = slides[index]
  const steps = times ? [0] : Array.from({ length: slide.steps + 1 }, (_, k) => k)
  for (const step of steps) {
    for (const time of times ?? [null]) {
      await page.evaluate(([i, s]) => {
        window.deck.go(i, s)
        window.deck.replay()
      }, [index, step])
      await page.waitForTimeout(time === null ? 200 : time * 1000)
      const name = `${pad(index + 1)}-${slide.id}${slide.steps && time === null ? `-s${step}` : ""}${time === null ? "" : `-t${time}`}.png`
      await page.screenshot({ path: path.join(outDir, name) })
    }
  }
  const issues = await layout(index)
  report.push({ slide: `${pad(index + 1)}-${slide.id}`, issues })
}
await browser.close()

const broken = report.filter((entry) => entry.issues.length)
for (const entry of broken) console.log(`${entry.slide}\n  ${entry.issues.join("\n  ")}`)
if (errors.length) console.log(`console errors:\n  ${[...new Set(errors)].join("\n  ")}`)
console.log(`${path.relative(ROOT, outDir)}: ${picks.length} slides, ${broken.length} with layout issues, ${errors.length} console errors`)
if (broken.length || errors.length) process.exit(1)
