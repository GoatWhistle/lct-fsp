import { gradeIcon } from "@/entities/catalog"
import type { CatalogTask } from "@/shared/api"
import { BackendText, useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { Button, Card, Chip, IconLabel } from "@/shared/ui"
import styles from "./task-card.module.css"

export interface TaskCardProps {
  readonly task: CatalogTask
  readonly index: number
  readonly onAnswer: (task: CatalogTask) => void
}

export function TaskCard({ task, index, onAnswer }: TaskCardProps) {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const format = useFormatters()
  return (
    <Card
      as="article"
      motionIndex={index}
      className={styles.card}
      title={
        <span className={styles.heading}>
          <Chip icon={gradeIcon(task.grade.code)} tone="accent">
            {names.grade(task.grade)}
          </Chip>
          <Chip icon={task.kind === "reference" ? "check" : "edit"}>{t(`kind.${task.kind}`)}</Chip>
        </span>
      }
    >
      <BackendText as="p" className={styles.prompt}>
        {task.prompt}
      </BackendText>
      <ul className={styles.topics} aria-label={t("card.topics")}>
        {task.topics.map((topic) => (
          <li key={topic.code}>
            <Chip icon="topic">{names.topic(topic)}</Chip>
          </li>
        ))}
      </ul>
      <footer className={styles.footer}>
        <span className={styles.stats}>
          <IconLabel icon="candidates" tone="secondary" size="sm">
            {t("card.answers", { count: task.answers })}
          </IconLabel>
          <IconLabel icon="calendar" tone="secondary" size="sm">
            {format.date(task.created_at)}
          </IconLabel>
        </span>
        <Button variant="secondary" size="compact" icon="edit" onClick={() => onAnswer(task)}>
          {t("card.answer")}
        </Button>
      </footer>
    </Card>
  )
}
