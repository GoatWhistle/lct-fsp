import { describe, expect, it } from "vitest"
import { ICONS } from "@/shared/ui/primitives/icon/icons"

describe("icon registry", () => {
  it("maps every glyph to exactly one name", () => {
    const glyphs = Object.values(ICONS)
    expect(new Set(glyphs).size).toBe(glyphs.length)
  })

  it("uses kebab-case names", () => {
    for (const name of Object.keys(ICONS)) expect(name).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/)
  })
})
