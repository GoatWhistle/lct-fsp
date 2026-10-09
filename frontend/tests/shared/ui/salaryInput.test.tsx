import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { i18n } from "@/shared/i18n"
import common from "@/shared/i18n/locales/en/common.json"
import { SalaryInput } from "@/shared/ui"

describe("SalaryInput", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en")
  })

  it("labels both bounds and states the gross basis", () => {
    render(<SalaryInput label="Range" from={100000} to={150000} onChange={() => undefined} />)
    expect(screen.getByRole("group", { name: "Range" })).toBeTruthy()
    expect(screen.getByLabelText(common.money.fieldFrom)).toBeTruthy()
    expect(screen.getByLabelText(common.money.fieldTo)).toBeTruthy()
    expect(screen.getByText(common.money.basis)).toBeTruthy()
  })

  it("reports one bound with the other kept", () => {
    const onChange = vi.fn()
    render(<SalaryInput label="Range" from={100000} to={150000} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText(common.money.fieldTo), { target: { value: "200000" } })
    expect(onChange).toHaveBeenCalledWith(100000, 200000)
    fireEvent.change(screen.getByLabelText(common.money.fieldFrom), { target: { value: "90000" } })
    expect(onChange).toHaveBeenLastCalledWith(90000, 150000)
  })

  it("shows the error as an alert", () => {
    render(<SalaryInput label="Range" from={2} to={1} onChange={() => undefined} error="Order" />)
    expect(screen.getByRole("alert").textContent).toContain("Order")
  })
})
