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
  readonly description?: string | undefined
  readonly actions?: ReactNode
  readonly children: ReactNode
}

export function EditorSection({ id, title, description, actions, children }: EditorSectionProps) {
  return (
    <Card
      id={id}
      title={title}
      description={description}
      actions={actions}
      motionIndex={ORDER.indexOf(id)}
      className={styles.section}
      data-section={id}
    >
      {children}
    </Card>
  )
}

export function FieldRow({ children }: { readonly children: ReactNode }) {
  return <div className={styles.row}>{children}</div>
}
