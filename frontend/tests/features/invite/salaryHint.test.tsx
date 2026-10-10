import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SalaryHint } from "@/features/invite/salary-hint/salary-hint"
import type { SalaryHint as Hint } from "@/shared/api"
import { i18n, LocaleProvider } from "@/shared/i18n"
import selection from "@/shared/i18n/locales/en/selection.json"

const state: { data: Hint | undefined } = { data: undefined }

vi.mock("@/entities/selection", () => ({
  useSalaryHint: () => ({ data: state.data }),
}))

function hint(changes: Partial<Hint>): Hint {
  return {
    salary_basis: "gross",
    available: true,
    probability: 0.42,
    evaluated_from: 100000,
    evaluated_to: 150000,
    target_probability: 0.6,
    reachable: true,
    hint_from: 180000,
    hint_to: 230000,
    rounding: 10000,
    ...changes,
  }
}

function view(onApply = vi.fn()) {
  return {
    onApply,
    ...render(
      <LocaleProvider>
        <SalaryHint selectionId="s1" candidateId="c1" from={100000} to={150000} onApply={onApply} />
      </LocaleProvider>,
    ),
  }
}

beforeEach(async () => {
  state.data = undefined
  await i18n.changeLanguage("en")
})

describe("SalaryHint", () => {
  it("renders nothing while there is no answer", () => {
    const { container } = view()
    expect(container.textContent).toBe("")
  })

  it("renders nothing without a model: no hint and no error", () => {
    state.data = hint({
      available: false,
      probability: null,
      evaluated_from: null,
      evaluated_to: null,
      target_probability: null,
      reachable: false,
      hint_from: null,
      hint_to: null,
      rounding: null,
    })
    const { container } = view()
    expect(container.textContent).toBe("")
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("shows the probability and applies the suggested range", () => {
    state.data = hint({})
    const { onApply } = view()
    expect(document.body.textContent).toContain("20–50%")
    expect(document.body.textContent).toContain("rather unlikely")
    expect(document.body.textContent).toContain("50–80%")
    expect(document.body.textContent).toContain("rather likely")
    expect(document.body.textContent).toContain("180")
    fireEvent.click(screen.getByRole("button", { name: selection.invite.hint.apply }))
    expect(onApply).toHaveBeenCalledWith(180000, 230000)
  })

  it("says the target is unreachable and offers no range", () => {
    state.data = hint({ reachable: false, hint_from: null, hint_to: null })
    view()
    expect(document.body.textContent).toContain("cannot be reached")
    expect(screen.queryByRole("button", { name: selection.invite.hint.apply })).toBeNull()
  })

  it("does not offer to change a range that already reaches the target", () => {
    state.data = hint({ probability: 0.7, hint_from: 90000, hint_to: 140000 })
    view()
    expect(screen.queryByRole("button", { name: selection.invite.hint.apply })).toBeNull()
  })
})
