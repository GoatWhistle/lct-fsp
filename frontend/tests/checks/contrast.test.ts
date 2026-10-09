import { describe, expect, it } from "vitest"
import { contrast, surfaceLadder } from "../../scripts/checks/rules/unityTokens.ts"
import type { SourceFile } from "../../scripts/checks/types.ts"

const tokens = (name: string, text: string): SourceFile => ({
  path: `src/shared/styles/tokens/${name}`,
  text,
})

const PALETTE = tokens(
  "palette.css",
  ":root { --white: #ffffff; --ink: #1b1c21; --mist: #f5f5f8; --blue: #402fff; --bright: #6355ff; --light: #9b93ff; --smoke: #ededed; --ash: #c8c9ca; --soft: #55565c; --deep: #131418; --raised: #222329; }",
)

const LIGHT = `
  --surface-canvas: var(--mist); --surface-card: var(--white);
  --surface-tint: color-mix(in oklab, var(--white), var(--blue) 7%);
  --surface-selected: color-mix(in oklab, var(--white), var(--blue) 9%);
  --surface-inverse: var(--ink); --surface-sidebar: var(--ink); --surface-focus: var(--ink);
  --surface-brand: var(--blue); --surface-tooltip: var(--ink);
  --surface-card-hover: color-mix(in oklab, var(--white), var(--ink) 4%);
  --surface-tint-hover: color-mix(in oklab, var(--white), var(--blue) 12%);
  --text-primary: var(--ink); --text-secondary: var(--soft); --text-accent: var(--blue);
  --text-disabled: var(--ash); --text-on-action: var(--white); --text-on-action-dark: var(--smoke);
  --text-on-brand: var(--white); --text-on-tooltip: var(--smoke); --text-on-inverse: var(--smoke);
  --text-on-inverse-secondary: var(--ash);
  --action-primary: var(--blue); --action-danger: #d01730; --action-dark: var(--ink);
  --focus-ring-color: var(--blue); --data-level: var(--blue);
  --border-input: color-mix(in oklab, var(--ink) 56%, transparent);`

const DARK = `
  --surface-canvas: var(--ink); --surface-card: var(--raised);
  --surface-tint: color-mix(in oklab, var(--raised), var(--blue) 18%);
  --surface-selected: color-mix(in oklab, var(--raised), var(--blue) 22%);
  --text-primary: var(--smoke); --text-secondary: var(--ash); --text-accent: var(--light);
  --text-on-action-dark: var(--ink); --action-dark: var(--smoke); --action-primary: var(--bright);
  --focus-ring-color: var(--light); --data-level: var(--light);
  --border-input: color-mix(in oklab, var(--smoke) 46%, transparent);`

const INVERSE = `--text-primary: var(--smoke); --text-secondary: var(--ash); --text-accent: var(--light); --focus-ring-color: var(--light);`

const semantic = (light = "", dark = "", inverse = "") =>
  tokens(
    "semantic.css",
    `:root,\n:root[data-theme="light"] {${LIGHT} ${light}\n}\n\n:root[data-theme="dark"] {${DARK} ${dark}\n}\n\n[data-surface="inverse"] {${INVERSE} ${inverse}\n}\n`,
  )

const messages = (light = "", dark = "", inverse = "") =>
  contrast.run([PALETTE, semantic(light, dark, inverse)]).map((violation) => violation.message)

describe("contrast and surface-ladder", () => {
  it("passes readable text in both themes and on inverse surfaces", () => {
    const files = [PALETTE, semantic()]
    expect([...contrast.run(files), ...surfaceLadder.run(files)]).toEqual([])
  })

  it("checks every --text-* token in the light theme", () => {
    expect(messages("--text-tertiary: var(--ash);")).toEqual(
      expect.arrayContaining([expect.stringContaining("light: --text-tertiary on --surface-card")]),
    )
  })

  it("checks the dark theme separately", () => {
    expect(messages("", "--text-accent: var(--blue);")).toEqual(
      expect.arrayContaining([expect.stringContaining("dark: --text-accent on --surface-card")]),
    )
  })

  it("checks text on inverse surfaces", () => {
    expect(messages("", "", "--text-secondary: var(--soft);")).toEqual(
      expect.arrayContaining([
        expect.stringContaining("inverse: --text-secondary on --surface-sidebar"),
      ]),
    )
  })

  it("resolves color-mix and blends translucent borders over the surface", () => {
    expect(messages("--border-input: color-mix(in oklab, var(--ink) 12%, transparent);")).toEqual(
      expect.arrayContaining([expect.stringContaining("light: --border-input on --surface-card")]),
    )
  })

  it("reports a dark action whose text matches it", () => {
    expect(messages("", "--text-on-action-dark: var(--smoke);")).toEqual([
      expect.stringContaining("dark: --text-on-action-dark on --action-dark"),
    ])
  })

  it("reports uneven surfaces and missing tokens", () => {
    const files = [
      PALETTE,
      semantic("--surface-tint: var(--white); --surface-card-hover: var(--mist);"),
    ]
    expect(surfaceLadder.run(files)).toHaveLength(2)
    expect(contrast.run([PALETTE])).toHaveLength(1)
  })
})
