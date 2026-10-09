import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import type { Rgba } from "./checks/color.ts"
import { resolveName, themeTables } from "./checks/themes.ts"
import { TOKENS_DIR } from "./checks/types.ts"

export const TOKEN_FILES = [
  "palette.css",
  "semantic.css",
  "typography.css",
  "space.css",
  "radius.css",
  "elevation.css",
  "motion.css",
  "keyframes.css",
] as const

export const FONT_PACKAGES = [
  "@fontsource-variable/onest",
  "@fontsource-variable/jetbrains-mono",
] as const

export interface TokenSource {
  readonly name: string
  readonly text: string
}

const COMMENT = /\/\*[\s\S]*?\*\//g
const ABSOLUTE_FONT_URL = /url\("\/fonts\//g
const PACKAGE_FONT_URL = /url\(\.\/files\/([\w.-]+)\)/g
const KEPT_FACE = /\/\*\s*[\w-]+?-(latin|latin-ext|cyrillic|cyrillic-ext)-wght-normal\s*\*\/\s*$/
const SEMANTIC_NAME = /^--(surface|text|action|border|data|fsp)-/
const CHANNEL_MAX = 255

export function buildTokenCss(sources: readonly TokenSource[]): string {
  const ordered = TOKEN_FILES.map((name) => sources.find((source) => source.name === name))
  const missing = TOKEN_FILES.filter((_, index) => ordered[index] === undefined)
  if (missing.length > 0) throw new Error(`missing token files: ${missing.join(", ")}`)
  return `${ordered
    .map((source) =>
      (source?.text ?? "").replace(COMMENT, "").replace(ABSOLUTE_FONT_URL, 'url("fonts/').trim(),
    )
    .join("\n\n")}\n`
}

export function pickFontFaces(css: string): { readonly css: string; readonly files: string[] } {
  const parts = css.split("@font-face")
  const kept = parts.slice(1).filter((_, index) => KEPT_FACE.test(parts[index] ?? ""))
  const files = kept.flatMap((block) =>
    [...block.matchAll(PACKAGE_FONT_URL)].map((match) => match[1] ?? ""),
  )
  const text = kept
    .map((block) => {
      const body = block.slice(0, block.indexOf("}") + 1).trim()
      return `@font-face ${body.replace(PACKAGE_FONT_URL, 'url("fonts/$1")')}`
    })
    .join("\n")
  return { css: text, files }
}

function hex(color: Rgba): string {
  const channel = (value: number) =>
    Math.round(Math.min(CHANNEL_MAX, Math.max(0, value)))
      .toString(16)
      .padStart(2, "0")
  const base = `#${channel(color.r)}${channel(color.g)}${channel(color.b)}`
  return color.a >= 1 ? base : `${base}${channel(color.a * CHANNEL_MAX)}`
}

export function lightColors(sources: readonly TokenSource[]): Record<string, string> {
  const files = sources.map((source) => ({
    path: `${TOKENS_DIR}${source.name}`,
    text: source.text,
  }))
  const table = themeTables(files).light
  const colors: Record<string, string> = {}
  for (const name of table.keys()) {
    if (!SEMANTIC_NAME.test(name)) continue
    const color = resolveName(table, name)
    if (color !== null) colors[name.slice(2)] = hex(color)
  }
  return colors
}

export function exportTokens(frontendRoot: string, targetDir: string): string {
  const tokensDir = join(frontendRoot, "src", "shared", "styles", "tokens")
  const sources = TOKEN_FILES.map((name) => ({
    name,
    text: readFileSync(join(tokensDir, name), "utf8"),
  }))
  mkdirSync(join(targetDir, "fonts"), { recursive: true })
  const faces = FONT_PACKAGES.map((name) => {
    const packageDir = join(frontendRoot, "node_modules", ...name.split("/"))
    const picked = pickFontFaces(readFileSync(join(packageDir, "index.css"), "utf8"))
    for (const file of picked.files)
      copyFileSync(join(packageDir, "files", file), join(targetDir, "fonts", file))
    return picked.css
  })
  const css = `${faces.join("\n")}\n\n${buildTokenCss(sources)}`
  writeFileSync(join(targetDir, "tokens.css"), css)
  const json = {
    theme: "light",
    fonts: { ui: "Onest Variable", mono: "JetBrains Mono Variable" },
    colors: lightColors(sources),
  }
  writeFileSync(join(targetDir, "tokens.json"), `${JSON.stringify(json, null, 2)}\n`)
  return css
}

export function exportPrint(frontendRoot: string, targetDir: string): void {
  const tokensDir = join(frontendRoot, "src", "shared", "styles", "tokens")
  const sources = TOKEN_FILES.map((name) => ({
    name,
    text: readFileSync(join(tokensDir, name), "utf8"),
  }))
  mkdirSync(targetDir, { recursive: true })
  const tokens = { colors: lightColors(sources) }
  writeFileSync(join(targetDir, "tokens.json"), `${JSON.stringify(tokens, null, 2)}\n`)
  const locales = join(frontendRoot, "src", "shared", "i18n", "locales")
  for (const locale of ["ru", "en"]) {
    const catalog = readFileSync(join(locales, locale, "catalog.json"), "utf8")
    writeFileSync(join(targetDir, `catalog.${locale}.json`), catalog)
  }
}

const frontendRoot = resolve(fileURLToPath(new URL("..", import.meta.url)))
const backendBrand = join(frontendRoot, "..", "backend", "app", "adapter", "brand")
if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv[2] === "--print") {
    const target = resolve(process.argv[3] ?? backendBrand)
    exportPrint(frontendRoot, target)
    process.stdout.write(`print tokens exported to ${target}\n`)
  } else {
    const target = resolve(process.argv[2] ?? join(frontendRoot, "dist-tokens"))
    exportTokens(frontendRoot, target)
    process.stdout.write(`tokens exported to ${target}\n`)
  }
}
