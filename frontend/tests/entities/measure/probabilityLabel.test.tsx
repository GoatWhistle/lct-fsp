import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"
import { ProbabilityLabel, type ProbabilityLabelProps } from "@/entities/measure"
import { i18n, LocaleProvider } from "@/shared/i18n"

function show(value: number, options: Pick<ProbabilityLabelProps, "lowData" | "verdict"> = {}) {
  return render(
    <LocaleProvider>
      <ProbabilityLabel value={value} {...options} />
    </LocaleProvider>,
  )
}

beforeEach(async () => {
  await i18n.changeLanguage("en")
})

describe("ProbabilityLabel", () => {
  it.each([
    [0.19, "0–20%", "unlikely"],
    [0.2, "20–50%", "rather unlikely"],
    [0.5, "50–80%", "rather likely"],
    [0.8, "80–100%", "very likely"],
  ] as const)("shows an interval and words for %s", (value, range, words) => {
    show(value)
    expect(screen.getByText(range)).toBeTruthy()
    expect(screen.getByText(words)).toBeTruthy()
  })

  it("replaces the estimate wording when there is too little data", () => {
    show(0.9, { lowData: true, verdict: "confidently_above" })
    expect(screen.getByText("80–100%")).toBeTruthy()
    expect(screen.getByText("not enough data")).toBeTruthy()
  })

  it("uses the backend's calibrated topic verdict", () => {
    show(0.8, { verdict: "confidently_above" })
    expect(screen.getByText("confidently above the requirement")).toBeTruthy()
  })
})
