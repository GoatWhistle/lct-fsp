import type { ReactNode } from "react"
import { COMPANY_DIALOG_LINK } from "@/entities/company"
import { TaskCard } from "@/features/task-editor"
import type { RegularTask } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState } from "@/shared/ui"
import styles from "./task-grid.module.css"

export type TaskFilter = "active" | "review" | "withdrawn"

export interface TaskGridProps {
  readonly tasks: readonly RegularTask[]
  readonly filter: TaskFilter
  readonly awaiting: ReadonlySet<string>
  readonly noCompany: boolean
  readonly create: ReactNode
  readonly onEdit: (task: RegularTask) => void
}

export function TaskGrid({ tasks, filter, awaiting, noCompany, create, onEdit }: TaskGridProps) {
  const { t } = useTranslation("taskEditor")
  if (tasks.length === 0) {
    const action = noCompany ? (
      <ButtonLink to={COMPANY_DIALOG_LINK} icon="company">
        {t("toCompany")}
      </ButtonLink>
    ) : filter === "active" ? (
      create
    ) : undefined
    return (
      <EmptyState
        icon={filter === "review" ? "accepted" : "task"}
        title={t(`empty.${filter}.title`)}
        description={t(noCompany ? "needCompany" : `empty.${filter}.text`)}
        action={action}
      />
    )
  }
  return (
    <div className={styles.grid}>
      {tasks.map((task, index) => (
        <TaskCard
          key={task.id}
          task={task}
          awaiting={awaiting.has(task.id)}
          index={index}
          onEdit={onEdit}
        />
      ))}
    </div>
  )
}
