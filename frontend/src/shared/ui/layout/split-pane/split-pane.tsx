import { clsx } from "clsx"
import {
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  useRef,
  useState,
} from "react"
import styles from "./split-pane.module.css"

const MIN = 30
const MAX = 70
const STEP = 5
const PERCENT = 100

export interface SplitPaneProps {
  readonly start: ReactNode
  readonly end: ReactNode
  readonly label: string
  readonly initial?: number
  readonly className?: string | undefined
}

function clamp(value: number): number {
  return Math.min(MAX, Math.max(MIN, value))
}

export function SplitPane({ start, end, label, initial = 55, className }: SplitPaneProps) {
  const [share, setShare] = useState(initial)
  const root = useRef<HTMLDivElement | null>(null)
  const dragging = useRef(false)

  const moveTo = (clientX: number) => {
    const box = root.current?.getBoundingClientRect()
    if (box === undefined || box.width === 0) return
    setShare(clamp(((clientX - box.left) / box.width) * PERCENT))
  }

  const onPointerDown = (event: PointerEvent<HTMLHRElement>) => {
    dragging.current = true
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<HTMLHRElement>) => {
    if (dragging.current) moveTo(event.clientX)
  }
  const onPointerUp = () => {
    dragging.current = false
  }
  const onKeyDown = (event: KeyboardEvent<HTMLHRElement>) => {
    const delta = event.key === "ArrowLeft" ? -STEP : event.key === "ArrowRight" ? STEP : 0
    if (event.key === "Home") setShare(MIN)
    if (event.key === "End") setShare(MAX)
    if (delta === 0) return
    event.preventDefault()
    setShare((value) => clamp(value + delta))
  }

  return (
    <div
      ref={root}
      className={clsx(styles.split, className)}
      style={{ "--split": `${share}%` } as CSSProperties}
    >
      <div className={styles.start}>{start}</div>
      <hr
        className={styles.handle}
        aria-orientation="vertical"
        aria-label={label}
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        aria-valuenow={Math.round(share)}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      />
      <div className={styles.end}>{end}</div>
    </div>
  )
}
