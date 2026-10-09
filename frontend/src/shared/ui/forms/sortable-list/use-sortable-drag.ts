import { type PointerEvent, type RefObject, useRef, useState } from "react"

interface Drag {
  readonly index: number
  readonly startY: number
  readonly pointerId: number
  readonly offsets: readonly number[]
  readonly size: number
}

export interface SortableDrag {
  readonly dragging: number | null
  readonly target: number | null
  readonly start: (index: number) => (event: PointerEvent<HTMLElement>) => void
  readonly move: (event: PointerEvent<HTMLElement>) => void
  readonly end: () => void
}

function targetFor(drag: Drag, dy: number): number {
  const center = (drag.offsets[drag.index] ?? 0) + dy + drag.size / 2
  let target = 0
  drag.offsets.forEach((offset, index) => {
    if (center > offset) target = index
  })
  return target
}

export function useSortableDrag(
  listRef: RefObject<HTMLOListElement | null>,
  onMove: (from: number, to: number) => void,
): SortableDrag {
  const drag = useRef<Drag | null>(null)
  const [dragging, setDragging] = useState<number | null>(null)
  const [target, setTarget] = useState<number | null>(null)

  const rows = () => [...(listRef.current?.children ?? [])] as HTMLElement[]

  const paint = (dy: number, nextTarget: number) => {
    const current = drag.current
    if (current === null) return
    rows().forEach((row, index) => {
      if (index === current.index) {
        row.style.transform = `translateY(${dy}px)`
        return
      }
      const between =
        current.index < nextTarget
          ? index > current.index && index <= nextTarget
          : index < current.index && index >= nextTarget
      const shift = current.index < nextTarget ? -current.size : current.size
      row.style.transform = between ? `translateY(${shift}px)` : ""
    })
  }

  const start = (index: number) => (event: PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return
    const all = rows()
    const first = all[0]?.offsetTop ?? 0
    const gap = all.length > 1 ? (all[1]?.offsetTop ?? 0) - first - (all[0]?.offsetHeight ?? 0) : 0
    drag.current = {
      index,
      startY: event.clientY,
      pointerId: event.pointerId,
      offsets: all.map((row) => row.offsetTop - first),
      size: (all[index]?.offsetHeight ?? 0) + gap,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    setDragging(index)
    setTarget(index)
  }

  const move = (event: PointerEvent<HTMLElement>) => {
    const current = drag.current
    if (current === null || event.pointerId !== current.pointerId) return
    const dy = event.clientY - current.startY
    const next = targetFor(current, dy)
    setTarget(next)
    paint(dy, next)
  }

  const end = () => {
    const current = drag.current
    if (current === null) return
    for (const row of rows()) row.style.transform = ""
    drag.current = null
    setDragging(null)
    if (target !== null && target !== current.index) onMove(current.index, target)
    setTarget(null)
  }

  return { dragging, target, start, move, end }
}
