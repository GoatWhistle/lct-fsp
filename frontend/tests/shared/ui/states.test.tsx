import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import ru from "@/shared/i18n/locales/ru/common.json"
import { Disclosure, EmptyState, ErrorState, ScrollArea, Skeleton, Spinner } from "@/shared/ui"
import { readEdges } from "@/shared/ui/layout/scroll-area/scroll-area"
import { setReducedMotion } from "../../setup/motionEnvironment"

describe("Skeleton and Spinner", () => {
  it("renders hidden skeleton lines", () => {
    const { container } = render(<Skeleton lines={3} />)
    expect(container.querySelectorAll(".bone")).toHaveLength(3)
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true")
  })

  it("hides the spinner label normally and shows it under reduced motion", () => {
    const { rerender } = render(<Spinner label="loading map" />)
    expect(screen.getByText("loading map").className).toBe("visually-hidden")
    setReducedMotion(true)
    rerender(<Spinner label="loading map" key="reduced" />)
    expect(screen.getByRole("status").dataset.reduced).toBe("true")
    expect(screen.getByText("loading map").className).not.toBe("visually-hidden")
  })
})

describe("EmptyState and ErrorState", () => {
  it("slides in with a reduced-motion fade", () => {
    render(<EmptyState title="Nothing yet" icon="need" size="hero" />)
    const root = screen.getByText("Nothing yet").parentElement as HTMLElement
    expect(root.dataset.motion).toBe("fade")
    expect(root.classList).toContain("hero")
  })

  it("announces errors and retries", () => {
    const onRetry = vi.fn()
    render(<ErrorState title="Map failed" description="timeout" onRetry={onRetry} />)
    expect(screen.getByRole("alert")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: ru.action.retry }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

describe("Disclosure", () => {
  it("opens and closes through the details motion", () => {
    render(<Disclosure summary="Details">content</Disclosure>)
    const details = screen.getByText("Details").closest("details") as HTMLDetailsElement
    fireEvent.click(screen.getByText("Details"), { detail: 1 })
    expect(details.open).toBe(true)
    expect(details.dataset.state).toBe("open")
    fireEvent.click(screen.getByText("Details"), { detail: 0 })
    expect(details.open).toBe(false)
  })

  it("marks keyboard toggles as instant", () => {
    render(<Disclosure summary="Keys">content</Disclosure>)
    const details = screen.getByText("Keys").closest("details") as HTMLDetailsElement
    fireEvent.click(screen.getByText("Keys"), { detail: 0 })
    expect(details.open).toBe(true)
    expect(details.dataset.instant).toBe("true")
  })

  it("can start open", () => {
    render(
      <Disclosure summary="Open" defaultOpen>
        content
      </Disclosure>,
    )
    expect((screen.getByText("Open").closest("details") as HTMLDetailsElement).open).toBe(true)
  })
})

describe("ScrollArea", () => {
  it("reads its edges", () => {
    const viewport = { scrollTop: 0, clientHeight: 100, scrollHeight: 300 } as HTMLElement
    expect(readEdges(viewport)).toEqual({ atStart: true, atEnd: false })
    expect(readEdges({ ...viewport, scrollTop: 200 } as HTMLElement)).toEqual({
      atStart: false,
      atEnd: true,
    })
  })

  it("marks scrolling and edges on the root", () => {
    const { container } = render(
      <ScrollArea label="Journal">
        <p>row</p>
      </ScrollArea>,
    )
    const root = container.firstElementChild as HTMLElement
    expect(root.dataset.atStart).toBe("true")
    fireEvent.scroll(screen.getByRole("region", { name: "Journal" }))
    expect(root.dataset.scrolling).toBe("true")
  })
})
