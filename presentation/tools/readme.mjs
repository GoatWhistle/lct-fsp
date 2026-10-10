import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { ROOT } from "./assemble.mjs"
import { launch } from "./browser.mjs"

const REPO = path.resolve(ROOT, "..")
const SOURCE = path.join(ROOT, "readme", "assets.html")
const DATA = path.join(ROOT, "readme", "readme.json")
const OUT = path.join(REPO, "docs", "readme")
const README = path.join(REPO, "README.md")
const THEMES = ["light", "dark"]
const ROWS = ["buttons", "status", "stack", "nav"]
const MERMAID_INIT = /^%%\{init:.*\}%%\s*$/
const LINE = 660
const GAP = 6

const data = JSON.parse(fs.readFileSync(DATA, "utf8"))
const shell = fs.readFileSync(path.join(ROOT, "src", "shell.html"), "utf8")
const mark = /<template id="brand-mark">\s*([\s\S]*?)\s*<\/template>/.exec(shell)?.[1] ?? ""

const items = {
  buttons: (data.buttons ?? []).map((b) => ({ ...b, asset: `cta-${b.name}`, alt: b.label })),
  status: (data.status ?? []).map((b, i) => ({ ...b, asset: `badge-status-${i + 1}`, alt: [b.label, b.value].filter(Boolean).join(": ") })),
  stack: (data.stack ?? []).map((b, i) => ({ ...b, asset: `badge-stack-${i + 1}`, alt: [b.label, b.value].filter(Boolean).join(": ") })),
  nav: (data.nav ?? []).map((b, i) => ({ ...b, asset: `badge-nav-${i + 1}`, alt: b.value })),
}

fs.mkdirSync(OUT, { recursive: true })
for (const file of fs.readdirSync(OUT)) {
  if (/^(cta|badge|facts|stack)-?.*\.png$/.test(file)) fs.rmSync(path.join(OUT, file))
}

const browser = await launch()
const page = await browser.newPage({ viewport: { width: 1100, height: 1600 }, deviceScaleFactor: 2 })
await page.goto(pathToFileURL(SOURCE).href)
await page.evaluate(
  ({ svg, rows }) => {
    for (const host of document.querySelectorAll("[data-mark]")) host.innerHTML = svg
    const target = document.getElementById("generated")
    const icon = (name) => document.querySelector(`#icons [data-icon="${name}"]`)?.cloneNode(true)
    const part = (cls, text) => {
      const span = document.createElement("span")
      span.className = cls
      const inner = document.createElement("span")
      inner.className = "text"
      inner.textContent = text
      span.append(inner)
      return span
    }
    for (const b of rows.buttons) {
      const el = document.createElement("span")
      el.className = `cta${b.primary ? " is-primary" : ""}`
      el.dataset.asset = b.asset
      const svg = icon(b.icon)
      if (svg) el.append(svg)
      el.append(part("text", b.label))
      target.append(el)
    }
    for (const kind of ["status", "stack", "nav"]) {
      for (const b of rows[kind]) {
        const el = document.createElement("span")
        el.className = ["badge", kind === "nav" ? "is-nav" : "", b.tone ? `is-${b.tone}` : ""].filter(Boolean).join(" ")
        el.dataset.asset = b.asset
        if (b.label) el.append(part("label", b.label))
        el.append(part("value", b.value))
        target.append(el)
      }
    }
  },
  { svg: mark, rows: items },
)
await page.evaluate(() => document.fonts.ready)
await page.evaluate(() => {
  const canvas = document.createElement("canvas").getContext("2d")
  for (const asset of document.querySelectorAll("#generated [data-asset]")) {
    const texts = [...asset.querySelectorAll(".text")]
    const shifts = texts.map((el) => {
      const style = getComputedStyle(el)
      canvas.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
      const cap = canvas.measureText("H").actualBoundingBoxAscent
      return Math.max(...texts.map((t) => canvas.measureText(t.textContent).actualBoundingBoxAscent)) - cap
    })
    const shift = Math.min(0, ...shifts) / 2
    for (const el of texts) el.style.transform = `translateY(${shift.toFixed(2)}px)`
  }
})

const sizes = {}
for (const theme of THEMES) {
  await page.evaluate((value) => {
    document.documentElement.dataset.theme = value
  }, theme)
  await page.evaluate(() => document.fonts.ready)
  const assets = page.locator("[data-asset]")
  const count = await assets.count()
  for (let i = 0; i < count; i += 1) {
    const name = await assets.nth(i).getAttribute("data-asset")
    await assets.nth(i).screenshot({ path: path.join(OUT, `${name}.${theme}.png`), omitBackground: true })
    const box = await assets.nth(i).boundingBox()
    sizes[name] = { width: Math.round(box.width), height: Math.round(box.height) }
  }
}

await page.evaluate(() => {
  document.documentElement.dataset.theme = "light"
})
const palette = await page.evaluate(() => {
  const probe = document.createElement("span")
  document.body.append(probe)
  const canvas = document.createElement("canvas").getContext("2d")
  const hex = (name) => {
    probe.style.color = `var(${name})`
    canvas.fillStyle = "#000"
    canvas.fillStyle = getComputedStyle(probe).color
    return canvas.fillStyle
  }
  const value = {
    primaryColor: hex("--surface-raised"),
    primaryTextColor: hex("--text-primary"),
    primaryBorderColor: hex("--action-primary"),
    secondaryColor: hex("--surface-sunken"),
    tertiaryColor: hex("--surface-base"),
    lineColor: hex("--text-muted"),
    textColor: hex("--text-primary"),
    noteBkgColor: hex("--surface-sunken"),
    noteTextColor: hex("--text-secondary"),
    actorBkg: hex("--surface-raised"),
    actorBorder: hex("--action-primary"),
    fontFamily: getComputedStyle(document.body).fontFamily.split(",")[0].replaceAll('"', "").trim(),
  }
  probe.remove()
  return value
})
await browser.close()

const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;")
const picture = (name, alt) => {
  const { width, height } = sizes[name]
  return `<picture><source media="(prefers-color-scheme: dark)" srcset="docs/readme/${name}.dark.png"><img src="docs/readme/${name}.light.png" alt="${escape(alt)}" width="${width}" height="${height}"></picture>`
}
const tag = (b) => (b.href ? `  <a href="${escape(b.href)}">${picture(b.asset, b.alt)}</a>` : `  ${picture(b.asset, b.alt)}`)
const span = (line) => line.reduce((sum, b) => sum + sizes[b.asset].width, 0) + GAP * Math.max(0, line.length - 1)
const fill = (list, limit) => {
  const lines = [[]]
  for (const b of list) {
    if (lines.at(-1).length && span([...lines.at(-1), b]) > limit) lines.push([])
    lines.at(-1).push(b)
  }
  return lines
}
const balance = (list) => {
  const count = fill(list, LINE).length
  let low = Math.max(...list.map((b) => sizes[b.asset].width))
  let high = LINE
  while (high - low > 1) {
    const mid = Math.floor((low + high) / 2)
    if (fill(list, mid).length <= count) high = mid
    else low = mid
  }
  return fill(list, high)
}
const row = (list) =>
  list.length
    ? balance(list)
        .map((line) => line.map(tag).join("\n"))
        .join("\n  <br>\n")
    : ""

let readme = fs.readFileSync(README, "utf8")
for (const kind of ROWS) {
  const block = new RegExp(`(<!-- readme:${kind} -->)[\\s\\S]*?(<!-- /readme:${kind} -->)`)
  if (!block.test(readme)) {
    console.error(`README.md: markers <!-- readme:${kind} --> … <!-- /readme:${kind} --> not found, row skipped`)
    continue
  }
  readme = readme.replace(block, (match, open, close) => `${open}\n${row(items[kind])}\n  ${close}`)
}
for (const name of ["banner", "mark"]) {
  const tag = new RegExp(`<img src="docs/readme/${name}\\.light\\.png"([^>]*?)\\s*/?>`, "g")
  readme = readme.replace(tag, (match, attrs) => {
    const rest = attrs.replace(/\s(width|height)="[^"]*"/g, "")
    return `<img src="docs/readme/${name}.light.png"${rest} width="${sizes[name].width}" height="${sizes[name].height}">`
  })
}
fs.writeFileSync(README, readme)

const init = `%%{init: ${JSON.stringify({ theme: "base", themeVariables: palette })}}%%`
const markdown = [README]
const collect = (dir) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory() && !entry.name.startsWith(".")) collect(full)
    else if (entry.isFile() && entry.name.endsWith(".md")) markdown.push(full)
  }
}
collect(path.join(REPO, "docs"))
let blocks = 0
for (const file of markdown) {
  const lines = fs.readFileSync(file, "utf8").split("\n")
  const out = []
  for (let i = 0; i < lines.length; i += 1) {
    out.push(lines[i])
    if (lines[i].trim() !== "```mermaid") continue
    blocks += 1
    out.push(init)
    if (MERMAID_INIT.test(lines[i + 1] ?? "")) i += 1
  }
  if (out.join("\n") !== lines.join("\n")) fs.writeFileSync(file, out.join("\n"))
}

const counts = ROWS.map((kind) => `${kind} ${items[kind].length}`).join(", ")
console.log(`docs/readme: banner, mark, ${counts}; light and dark at 2x`)
console.log(`README rows rebuilt from readme/readme.json; mermaid blocks themed: ${blocks}`)
