import { clsx } from "clsx"
import type { ReactNode } from "react"
import styles from "./page-body.module.css"

export interface PageBodyProps {
  readonly className?: string | undefined
  readonly children: ReactNode
}

export function PageBody({ className, children }: PageBodyProps) {
  return <div className={clsx(styles.body, className)}>{children}</div>
}
