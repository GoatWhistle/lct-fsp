import { mixOklab, parseHex, percentOf, type Rgba, withAlpha } from "./color.ts"
import { type SourceFile, TOKENS_DIR } from "./types.ts"

export type ThemeName = "light" | "dark" | "inverse"

export type ThemeTables = Readonly<Record<ThemeName, ReadonlyMap<string, string>>>

const COLOR_FILES = ["palette.css", "semantic.css", "elevation.css"]
const BLOCK = /([^{}]+)\{([^{}]*)\}/g
const DECLARATION = /(--[\w-]+)\s*:\s*([^;]+);/g
const VAR_ONLY = /^var\((--[\w-]+)\)$/
const MIX = /^color-mix\(in oklab,\s*(.+)\)$/
const MAX_DEPTH = 10

type Scope = "base" | "dark" | "inverse" | "other"

function scopeOf(selector: string): Scope {
  if (selector.includes('[data-theme="dark"]')) return "dark"
  if (selector.includes('[data-surface="inverse"]')) return "inverse"
  if (selector.includes("[data-surface")) return "other"
  return selector.includes(":root") ? "base" : "other"
}

export function themeTables(files: readonly SourceFile[]): ThemeTables {
  const scopes: Record<Scope, Map<string, string>> = {
    base: new Map(),
    dark: new Map(),
    inverse: new Map(),
    other: new Map(),
  }
  for (const name of COLOR_FILES) {
    const file = files.find((item) => item.path === `${TOKENS_DIR}${name}`)
    if (file === undefined) continue
    for (const block of file.text.matchAll(BLOCK)) {
      const target = scopes[scopeOf(block[1] ?? "")]
      for (const declaration of (block[2] ?? "").matchAll(DECLARATION))
        target.set(declaration[1] ?? "", (declaration[2] ?? "").trim())
    }
  }
  return {
    light: scopes.base,
    dark: new Map([...scopes.base, ...scopes.dark]),
    inverse: new Map([...scopes.base, ...scopes.inverse]),
  }
}

function splitArguments(text: string): string[] {
  const parts: string[] = []
  let depth = 0
  let current = ""
  for (const char of text) {
    if (char === "(") depth += 1
    if (char === ")") depth -= 1
    if (char === "," && depth === 0) {
      parts.push(current.trim())
      current = ""
    } else current += char
  }
  parts.push(current.trim())
  return parts
}

interface Part {
  readonly color: Rgba | null
  readonly share: number | null
}

function partOf(table: ReadonlyMap<string, string>, text: string, depth: number): Part {
  const match = /^(.*?)\s+(\d+(?:\.\d+)?)%$/.exec(text)
  const expression = match === null ? text : (match[1] ?? "")
  const share = match === null ? null : percentOf(match[2] ?? "")
  return { color: resolveColor(table, expression, depth + 1), share }
}

function mixOf(table: ReadonlyMap<string, string>, inner: string, depth: number): Rgba | null {
  const [first, second] = splitArguments(inner).map((text) => partOf(table, text, depth))
  if (
    first?.color === null ||
    second?.color === null ||
    first === undefined ||
    second === undefined
  )
    return null
  if (second.color?.a === 0 && first.color !== null) return withAlpha(first.color, first.share ?? 1)
  const secondShare = second.share ?? (first.share === null ? 0.5 : 1 - first.share)
  return first.color === null || second.color === null
    ? null
    : mixOklab(first.color, second.color, secondShare)
}

export function resolveColor(
  table: ReadonlyMap<string, string>,
  value: string | undefined,
  depth = 0,
): Rgba | null {
  if (value === undefined || depth > MAX_DEPTH) return null
  const text = value.trim()
  if (text === "transparent") return { r: 0, g: 0, b: 0, a: 0 }
  const hex = parseHex(text)
  if (hex !== null) return hex
  const reference = VAR_ONLY.exec(text)
  if (reference !== null) return resolveColor(table, table.get(reference[1] ?? ""), depth + 1)
  const mix = MIX.exec(text)
  return mix === null ? null : mixOf(table, mix[1] ?? "", depth)
}

export function resolveName(table: ReadonlyMap<string, string>, name: string): Rgba | null {
  return resolveColor(table, table.get(name))
}
