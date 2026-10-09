import { type RefObject, useLayoutEffect, useRef } from "react"

export interface VerticalIndicator {
  readonly listRef: RefObject<HTMLUListElement | null>
  readonly indicatorRef: RefObject<HTMLSpanElement | null>
}

export function useVerticalIndicator(
  activeKey: string | null,
  layoutKey: string,
): VerticalIndicator {
  const listRef = useRef<HTMLUListElement | null>(null)
  const indicatorRef = useRef<HTMLSpanElement | null>(null)
  const placed = useRef(false)

  useLayoutEffect(() => {
    const list = listRef.current
    const indicator = indicatorRef.current
    if (list === null || indicator === null) return
    const item =
      activeKey === null ? null : list.querySelector<HTMLElement>(`[data-nav="${activeKey}"]`)
    if (item === null) {
      indicator.dataset.visible = "false"
      return
    }
    indicator.dataset.instant = placed.current ? "false" : "true"
    indicator.style.transform = `translateY(${item.offsetTop}px)`
    indicator.style.blockSize = `${item.offsetHeight}px`
    indicator.dataset.visible = "true"
    indicator.dataset.layout = layoutKey
    placed.current = true
  }, [activeKey, layoutKey])

  return { listRef, indicatorRef }
}
