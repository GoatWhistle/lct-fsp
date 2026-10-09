import { clsx } from "clsx"
import { type ReactNode, useId } from "react"
import styles from "./pane.module.css"

export interface PaneProps {
  readonly title: string
  readonly leading?: ReactNode
  readonly meta?: ReactNode
  readonly tone?: "canvas" | "inverse"
  readonly className?: string | undefined
  readonly children: ReactNode
}

export function Pane({ title, leading, meta, tone = "canvas", className, children }: PaneProps) {
  const titleId = useId()
  return (
    <section
      className={clsx(styles.pane, className)}
      data-tone={tone}
      data-surface={tone === "inverse" ? "inverse" : undefined}
      aria-labelledby={titleId}
    >
      <header className={styles.head}>
        {leading}
        <div className={styles.titles}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {meta}
        </div>
      </header>
      {children}
    </section>
  )
}
