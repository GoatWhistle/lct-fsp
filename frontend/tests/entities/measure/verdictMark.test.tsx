import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"
import { VerdictMark } from "@/entities/measure"
import { i18n, LocaleProvider } from "@/shared/i18n"

beforeEach(async () => {
  await i18n.changeLanguage("en")
})

describe("VerdictMark", () => {
  it("shows the topic probability as an interval with the backend verdict", () => {
    render(
      <LocaleProvider>
        <VerdictMark verdict="likely_above" probability={0.67} />
      </LocaleProvider>,
    )
    expect(screen.getByText("50–80%")).toBeTruthy()
    expect(screen.getByText("likely above the requirement")).toBeTruthy()
    expect(document.body.textContent).not.toContain("67")
  })

  it("keeps the interval but says the data is thin", () => {
    render(
      <LocaleProvider>
        <VerdictMark verdict="below" probability={0.1} lowData />
      </LocaleProvider>,
    )
    expect(screen.getByText("0–20%")).toBeTruthy()
    expect(screen.getByText("not enough data")).toBeTruthy()
  })
})
