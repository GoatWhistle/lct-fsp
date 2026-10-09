import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { chromium, type Page } from "playwright-core"
import {
  FSP_MARK_BLUE,
  FSP_MARK_NEUTRAL,
  FSP_MARK_RED,
  FSP_MARK_VIEWBOX,
} from "../src/shared/ui/brand/fsp-mark/fsp-mark-paths.ts"
import { lightColors } from "./exportTokens.ts"

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)))
const PUBLIC = join(ROOT, "public")
const TOKENS = join(ROOT, "src", "shared", "styles", "tokens")
const LOCALES = join(ROOT, "src", "shared", "i18n", "locales")
const ICO_SIZES = [16, 32, 48] as const
const OG = { width: 1200, height: 630 } as const

interface Palette {
  readonly graphite: string
  readonly blue: string
  readonly bright: string
  readonly red: string
  readonly smoke: string
  readonly ash: string
  readonly dim: string
}

function palette(): Palette {
  const names = ["palette.css", "semantic.css", "elevation.css"]
  const colors = lightColors(
    names.map((name) => ({ name, text: readFileSync(join(TOKENS, name), "utf8") })),
  )
  const pick = (name: string) => {
    const value = colors[name]
    if (value === undefined) throw new Error(`missing color ${name}`)
    return value
  }
  return {
    graphite: pick("fsp-graphite"),
    blue: pick("fsp-blue"),
    bright: pick("fsp-blue-bright"),
    red: pick("fsp-red"),
    smoke: pick("fsp-smoke"),
    ash: pick("fsp-ash"),
    dim: pick("fsp-ash-dim"),
  }
}

interface MarkTone {
  readonly neutral: string
  readonly neutralDark?: string
  readonly background?: string
  readonly scale?: number
}

const MARK_SQUARE = "-5 -10 247 247"

export function markSvg(colors: Palette, tone: MarkTone): string {
  const adaptive =
    tone.neutralDark === undefined
      ? ""
      : `<style>@media (prefers-color-scheme: dark){.n{fill:${tone.neutralDark}}}</style>`
  const background =
    tone.background === undefined
      ? ""
      : `<rect x="-5" y="-10" width="247" height="247" fill="${tone.background}"/>`
  const scale = tone.scale ?? 1
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${MARK_SQUARE}"><title>calibr</title>${adaptive}${background}<g transform="translate(118.5 113.5) scale(${scale}) translate(-118.5 -113.5)"><path class="n" fill="${tone.neutral}" d="${FSP_MARK_NEUTRAL}"/><path fill="${colors.red}" d="${FSP_MARK_RED}"/><path fill="${colors.blue}" d="${FSP_MARK_BLUE}"/></g></svg>
`
}

function fspMarkSvg(colors: Palette): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${FSP_MARK_VIEWBOX}"><path fill="${colors.smoke}" d="${FSP_MARK_NEUTRAL}"/><path fill="${colors.red}" d="${FSP_MARK_RED}"/><path fill="${colors.blue}" d="${FSP_MARK_BLUE}"/></svg>`
}

function fontFace(family: string, file: string): string {
  const data = readFileSync(join(ROOT, "node_modules", "@fontsource-variable", file)).toString(
    "base64",
  )
  const source = `url(data:font/woff2;base64,${data}) format("woff2")`
  return `@font-face{font-family:"${family}";src:${source};font-weight:100 900;}`
}

function ogHtml(colors: Palette, title: string, lead: string, byline: string): string {
  const fonts =
    fontFace("Onest", "onest/files/onest-cyrillic-wght-normal.woff2") +
    fontFace("Onest", "onest/files/onest-latin-wght-normal.woff2") +
    fontFace("JBM", "jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2") +
    fontFace("JBM", "jetbrains-mono/files/jetbrains-mono-cyrillic-wght-normal.woff2")
  const ticks = [0.2, 0.4, 0.6, 0.8]
    .map((x) => `<span class="tick" style="left:${x * 100}%"></span>`)
    .join("")
  return `<!doctype html><html><head><meta charset="utf-8"><style>${fonts}
*{box-sizing:border-box;margin:0}
body{width:${OG.width}px;height:${OG.height}px;background:${colors.graphite};color:${colors.smoke};font-family:Onest;overflow:hidden;position:relative}
.top{position:absolute;left:72px;top:64px;display:flex;align-items:center;gap:14px}
.fsp{height:58px}
.word{font-family:JBM;font-weight:600;font-size:52px;letter-spacing:-0.04em}
.by{position:absolute;right:72px;top:84px;font-family:JBM;font-size:22px;color:${colors.ash}}
.title{position:absolute;left:72px;top:206px;width:880px;font-family:JBM;font-weight:500;font-size:68px;line-height:1.06;letter-spacing:-0.03em}
.lead{position:absolute;left:72px;top:400px;width:760px;font-size:26px;line-height:1.45;color:${colors.ash}}
.ruler{position:absolute;left:72px;right:72px;bottom:64px;height:14px;border-radius:7px;background:rgba(237,237,237,0.1)}
.tick{position:absolute;top:-6px;width:2px;height:26px;background:rgba(237,237,237,0.28)}
.band{position:absolute;left:61%;width:23%;top:0;bottom:0;border-radius:7px;background:rgba(99,85,255,0.45)}
.node{position:absolute;left:72%;top:50%;width:30px;height:30px;border-radius:50%;background:${colors.bright};border:4px solid ${colors.graphite};transform:translate(-50%,-50%)}
</style></head><body>
<div class="top">${fspMarkSvg(colors).replace("<svg", '<svg class="fsp"')}<span class="word">calibr</span></div>
<div class="by">${byline}</div>
<h1 class="title">${title}</h1>
<p class="lead">${lead}</p>
<div class="ruler">${ticks}<span class="band"></span><span class="node"></span></div>
</body></html>`
}

function ico(images: readonly { readonly size: number; readonly data: Buffer }[]): Buffer {
  const header = Buffer.alloc(6 + images.length * 16)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(images.length, 4)
  let offset = header.length
  images.forEach((image, index) => {
    const entry = 6 + index * 16
    header.writeUInt8(image.size >= 256 ? 0 : image.size, entry)
    header.writeUInt8(image.size >= 256 ? 0 : image.size, entry + 1)
    header.writeUInt16LE(1, entry + 4)
    header.writeUInt16LE(32, entry + 6)
    header.writeUInt32LE(image.data.length, entry + 8)
    header.writeUInt32LE(offset, entry + 12)
    offset += image.data.length
  })
  return Buffer.concat([header, ...images.map((image) => image.data)])
}

async function renderSvg(page: Page, svg: string, size: number): Promise<Buffer> {
  await page.setViewportSize({ width: size, height: size })
  await page.setContent(
    `<html><body style="margin:0;background:transparent">${svg.replace("<svg", `<svg width="${size}" height="${size}"`)}</body></html>`,
  )
  return page.screenshot({ omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } })
}

function words(locale: string) {
  const read = (name: string) =>
    JSON.parse(readFileSync(join(LOCALES, locale, `${name}.json`), "utf8"))
  const home = read("home") as { hero: { title: string; lead: string } }
  const common = read("common") as { app: { byFsp: string }; brand: { fspFull: string } }
  return {
    title: home.hero.title,
    lead: home.hero.lead,
    byFsp: common.app.byFsp,
    fsp: common.brand.fspFull,
  }
}

function manifest(colors: Palette): string {
  const ru = words("ru")
  return `${JSON.stringify(
    {
      name: ru.byFsp,
      short_name: "calibr",
      description: ru.title,
      lang: "ru",
      start_url: "/",
      display: "standalone",
      background_color: colors.graphite,
      theme_color: colors.graphite,
      icons: [
        { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
        {
          src: "/icons/icon-maskable-512.png",
          sizes: "512x512",
          type: "image/png",
          purpose: "maskable",
        },
        { src: "/favicon.svg", sizes: "any", type: "image/svg+xml" },
      ],
    },
    null,
    2,
  )}\n`
}

async function main(): Promise<void> {
  const colors = palette()
  const mark = markSvg(colors, { neutral: colors.dim, neutralDark: colors.smoke })
  const flat = markSvg(colors, { neutral: colors.dim })
  const tile = (scale: number) =>
    markSvg(colors, { neutral: colors.smoke, background: colors.graphite, scale })
  mkdirSync(join(PUBLIC, "icons"), { recursive: true })
  mkdirSync(join(PUBLIC, "brand"), { recursive: true })
  writeFileSync(join(PUBLIC, "favicon.svg"), mark)
  writeFileSync(join(PUBLIC, "site.webmanifest"), manifest(colors))
  const browser = await chromium.launch({ channel: "chrome" })
  try {
    const page = await browser.newPage({ deviceScaleFactor: 1 })
    const icoImages = []
    for (const size of ICO_SIZES) icoImages.push({ size, data: await renderSvg(page, flat, size) })
    writeFileSync(join(PUBLIC, "favicon.ico"), ico(icoImages))
    writeFileSync(join(PUBLIC, "apple-touch-icon.png"), await renderSvg(page, tile(0.74), 180))
    writeFileSync(join(PUBLIC, "icons", "icon-192.png"), await renderSvg(page, tile(0.8), 192))
    writeFileSync(join(PUBLIC, "icons", "icon-512.png"), await renderSvg(page, tile(0.8), 512))
    const maskable = tile(0.62)
    writeFileSync(
      join(PUBLIC, "icons", "icon-maskable-512.png"),
      await renderSvg(page, maskable, 512),
    )
    for (const locale of ["ru", "en"]) {
      const text = words(locale)
      await page.setViewportSize(OG)
      await page.setContent(ogHtml(colors, text.title, text.lead, text.fsp), { waitUntil: "load" })
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({
        path: join(PUBLIC, "brand", `og-${locale}.png`),
        clip: { x: 0, y: 0, ...OG },
      })
    }
  } finally {
    await browser.close()
  }
  process.stdout.write("brand assets written\n")
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main()
}
