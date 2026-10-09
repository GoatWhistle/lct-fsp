import { describe, expect, it } from "vitest"
import { factorBars } from "@/features/selection-board/selection-model"

describe("factorBars", () => {
  it("orders factors by size and scales them to the largest", () => {
    const bars = factorBars({
      base: -0.3,
      logit: 0.9,
      factors: [
        { factor: "grade", contribution: 0.1 },
        { factor: "salary", contribution: -0.8 },
        { factor: "match", contribution: 0.4 },
      ],
    })
    expect(bars.map((bar) => bar.factor)).toEqual(["salary", "match", "grade"])
    expect(bars.map((bar) => bar.share)).toEqual([1, 0.5, 0.125])
    expect(bars[0]?.contribution).toBe(-0.8)
  })

  it("survives all-zero contributions", () => {
    const bars = factorBars({ base: 0, logit: 0, factors: [{ factor: "city", contribution: 0 }] })
    expect(bars[0]?.share).toBe(0)
  })
})
