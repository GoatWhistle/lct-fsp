import type { ReactNode } from "react"
import { Card } from "@/shared/ui"
import styles from "./editor-section.module.css"

export type SectionId =
  | "resume"
  | "about"
  | "experience"
  | "contacts"
  | "stack"
  | "expectations"
  | "visibility"
  | "fsp"

const ORDER: readonly SectionId[] = [
  "resume",
  "about",
  "experience",
  "contacts",
  "stack",
  "expectations",
  "visibility",
  "fsp",
]

export interface EditorSectionProps {
  readonly id: SectionId
  readonly title: string
  readonly actions?: ReactNode
  readonly children: ReactNode
}

export function EditorSection({ id, title, actions, children }: EditorSectionProps) {
  return (
    <Card
      id={id}
      level="section"
      title={title}
      actions={actions}
      motionIndex={ORDER.indexOf(id)}
      className={styles.section}
      data-section={id}
    >
      <div className={styles.body}>{children}</div>
    </Card>
  )
}
