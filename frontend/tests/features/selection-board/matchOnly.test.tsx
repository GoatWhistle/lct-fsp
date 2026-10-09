import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { orderedKey, selectionKey } from "@/entities/selection"
import { SelectionBar } from "@/features/selection-board/selection-bar/selection-bar"
import type { Selection } from "@/shared/api"
import { i18n, LocaleProvider } from "@/shared/i18n"
import selectionText from "@/shared/i18n/locales/en/selection.json"

const selection = {
  stack_cap: 0.2,
  exact_total: 3,
  nearby_total: 1,
  unconfirmed_total: 0,
  filtered_exact_total: 3,
  filtered_nearby_total: 1,
  filtered_unconfirmed_total: 0,
} as Selection

function bar(matchOnly: boolean, onMatchOnly = vi.fn()) {
  render(
    <LocaleProvider>
      <SelectionBar
        selection={selection}
        shortlistCount={0}
        matchOnly={matchOnly}
        onMatchOnly={onMatchOnly}
        onOpenShortlist={() => undefined}
      />
    </LocaleProvider>,
  )
  return onMatchOnly
}

beforeEach(async () => {
  await i18n.changeLanguage("en")
})

describe("match only switch", () => {
  it("reflects the current order and asks to flip it", () => {
    const onMatchOnly = bar(false)
    const toggle = screen.getByRole("switch", { name: selectionText.order.matchOnly })
    expect(toggle.getAttribute("aria-checked")).toBe("false")
    fireEvent.click(toggle)
    expect(onMatchOnly).toHaveBeenCalledWith(true)
  })

  it("is on when the order is by match", () => {
    bar(true)
    const toggle = screen.getByRole("switch", { name: selectionText.order.matchOnly })
    expect(toggle.getAttribute("aria-checked")).toBe("true")
  })
})

describe("orderedKey", () => {
  it("keeps the saved order under the selection key and the other order apart", () => {
    expect(orderedKey("s", "mutual")).toEqual(selectionKey("s"))
    expect(orderedKey("s", "match")).not.toEqual(selectionKey("s"))
    expect(orderedKey("s", "match").slice(0, selectionKey("s").length)).toEqual(selectionKey("s"))
  })
})
