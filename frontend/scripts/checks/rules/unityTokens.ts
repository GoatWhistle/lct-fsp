import { ratioOf } from "../color.ts"
import { resolveName, type ThemeName, type ThemeTables, themeTables } from "../themes.ts"
import { resolveToken } from "../tokens.ts"
import { type Check, TOKENS_DIR, type Violation } from "../types.ts"

export const MIN_CONTRAST = 4.5
export const MIN_NON_TEXT_CONTRAST = 3

export const TEXT_SURFACES = [
  "--surface-canvas",
  "--surface-card",
  "--surface-tint",
  "--surface-selected",
]
export const INVERSE_SURFACES = ["--surface-sidebar", "--surface-focus"]
export const ON_SURFACES: Readonly<Record<string, readonly string[]>> = {
  "--text-on-action": ["--action-primary", "--action-danger"],
  "--text-on-action-dark": ["--action-dark"],
  "--text-on-brand": ["--surface-brand"],
  "--text-on-tooltip": ["--surface-tooltip"],
  "--text-on-inverse": ["--surface-inverse"],
  "--text-on-inverse-secondary": ["--surface-inverse"],
}
export const EXEMPT_TEXT = new Set(["--text-disabled"])
const NON_TEXT: ReadonlyArray<readonly [string, string]> = [
  ["--border-input", "--surface-card"],
  ["--border-input", "--surface-canvas"],
  ["--data-level", "--surface-card"],
  ["--action-primary", "--surface-card"],
]

type Pair = readonly [ThemeName, string, string, number]

function themePairs(theme: ThemeName, names: readonly string[]): Pair[] {
  const texts = names.filter((name) => name.startsWith("--text-") && !EXEMPT_TEXT.has(name))
  const plain = texts.filter((name) => !name.startsWith("--text-on-"))
  const surfaces = theme === "inverse" ? INVERSE_SURFACES : TEXT_SURFACES
  const textPairs = plain.flatMap((text) =>
    surfaces.map((surface): Pair => [theme, text, surface, MIN_CONTRAST]),
  )
  const rings = surfaces.map(
    (surface): Pair => [theme, "--focus-ring-color", surface, MIN_NON_TEXT_CONTRAST],
  )
  if (theme === "inverse") return [...textPairs, ...rings]
  const onPairs = Object.entries(ON_SURFACES).flatMap(([text, backs]) =>
    backs.map((back): Pair => [theme, text, back, MIN_CONTRAST]),
  )
  const fixed = NON_TEXT.map(([front, back]): Pair => [theme, front, back, MIN_NON_TEXT_CONTRAST])
  return [...textPairs, ...onPairs, ...rings, ...fixed]
}

export function contrastPairs(tables: ThemeTables): Pair[] {
  return (["light", "dark", "inverse"] as const).flatMap((theme) =>
    themePairs(theme, [...tables[theme].keys()]),
  )
}

const tokenViolation = (file: string, message: string): Violation => ({
  file: `${TOKENS_DIR}${file}`,
  message,
})

export const contrast: Check = {
  id: "contrast",
  run: (files) => {
    const tables = themeTables(files)
    if (!tables.light.has("--surface-card"))
      return [tokenViolation("semantic.css", "semantic tokens are missing")]
    return contrastPairs(tables).flatMap(([theme, front, back, minimum]): Violation[] => {
      const table = tables[theme]
      const foreground = resolveName(table, front)
      const background = resolveName(table, back)
      if (foreground === null || background === null)
        return [tokenViolation("semantic.css", `${theme}: cannot resolve ${front} on ${back}`)]
      const ratio = ratioOf(foreground, background)
      return ratio < minimum
        ? [tokenViolation("semantic.css", `${theme}: ${front} on ${back} is ${ratio.toFixed(2)}:1`)]
        : []
    })
  },
}

const SURFACES = ["--surface-canvas", "--surface-card", "--surface-tint", "--surface-inverse"]
const HOVER_STEP = /^color-mix\(in oklab, var\((--[\w-]+)\), var\(--[\w-]+\) (\d+)%\)$/
export const MAX_HOVER_STEP = 14

export const surfaceLadder: Check = {
  id: "surface-ladder",
  run: (files) => {
    const table = themeTables(files).light
    if (table.size === 0) return [tokenViolation("semantic.css", "semantic tokens are missing")]
    const resolved = SURFACES.map((name) => resolveToken(table, name))
    const found: Violation[] = []
    if (new Set(resolved).size !== SURFACES.length || resolved.includes(null)) {
      found.push(
        tokenViolation("semantic.css", "surfaces canvas, card, tint, inverse must be distinct"),
      )
    }
    for (const name of ["--surface-card-hover", "--surface-tint-hover"]) {
      const step = HOVER_STEP.exec(table.get(name) ?? "")
      if (step === null || Number(step[2]) > MAX_HOVER_STEP) {
        found.push(
          tokenViolation(
            "semantic.css",
            `${name} must mix its base with one palette colour by <= ${MAX_HOVER_STEP}%`,
          ),
        )
      }
    }
    return found
  },
}
