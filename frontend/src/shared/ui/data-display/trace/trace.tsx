import { clsx } from "clsx"
import type { CSSProperties, ReactNode } from "react"
import styles from "./trace.module.css"

export type TraceStatus = "done" | "current" | "upcoming"

export interface TraceStep {
  readonly key: string
  readonly title: ReactNode
  readonly description?: ReactNode
  readonly status: TraceStatus
}

export interface TraceProps {
  readonly steps: readonly TraceStep[]
  readonly orientation?: "horizontal" | "vertical"
  readonly label: string
  readonly animate?: boolean
  readonly className?: string | undefined
}

export function Trace({
  steps,
  orientation = "vertical",
  label,
  animate = false,
  className,
}: TraceProps) {
  return (
    <ol
      className={clsx(styles.trace, className)}
      data-orientation={orientation}
      data-animate={animate}
      aria-label={label}
    >
      {steps.map((step, index) => (
        <li
          key={step.key}
          className={styles.step}
          data-status={step.status}
          aria-current={step.status === "current" ? "step" : undefined}
          style={{ "--i": index } as CSSProperties}
        >
          <span className={styles.marker} aria-hidden="true">
            <span className={styles.node} />
            {index < steps.length - 1 && <span className={styles.line} />}
          </span>
          <span className={styles.content}>
            <span className={styles.title}>{step.title}</span>
            {step.description === undefined ? null : (
              <span className={styles.description}>{step.description}</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}
