import { clsx } from "clsx"
import { type ReactNode, useId } from "react"
import styles from "./section.module.css"

export type SectionTone = "canvas" | "card" | "inverse" | "brand"

export interface SectionProps {
  readonly title?: ReactNode
  readonly lead?: ReactNode
  readonly tone?: SectionTone
  readonly className?: string | undefined
  readonly children: ReactNode
}

const SURFACE: Readonly<Record<SectionTone, string | undefined>> = {
  canvas: undefined,
  card: undefined,
  inverse: "inverse",
  brand: "brand",
}

export function Section({ title, lead, tone = "canvas", className, children }: SectionProps) {
  const titleId = useId()
  return (
    <section
      className={clsx(styles.section, className)}
      data-tone={tone}
      data-surface={SURFACE[tone]}
      aria-labelledby={title === undefined ? undefined : titleId}
    >
      {title === undefined ? null : (
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {lead === undefined ? null : <p className={styles.lead}>{lead}</p>}
        </header>
      )}
      {children}
    </section>
  )
}
