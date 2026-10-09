import { useState } from "react"
import { usePath } from "@/entities/candidate-path"
import { useGrades, useSpecializations } from "@/entities/catalog"
import { useTaskCatalog } from "@/entities/task"
import type { CatalogTask } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Button, EmptyState, LoadError, Select, Skeleton } from "@/shared/ui"
import { AnswerDrawer } from "../answer-drawer/answer-drawer"
import { TaskCard } from "../task-card/task-card"
import styles from "./task-catalog.module.css"

const ALL = "all"

function useTopicOptions() {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const path = usePath()
  const specializations = useSpecializations()
  const code = path.data?.category?.specialization.code
  const topics = specializations.data?.find((item) => item.code === code)?.topics ?? []
  return [
    { value: ALL, label: t("filters.allTopics") },
    ...topics.map((topic) => ({ value: topic.code, label: names.topic(topic) })),
  ]
}

function useGradeOptions() {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const grades = useGrades()
  return [
    { value: ALL, label: t("filters.allGrades") },
    ...(grades.data ?? []).map((grade) => ({ value: grade.code, label: names.grade(grade) })),
  ]
}

interface ResultsProps {
  readonly tasks: readonly CatalogTask[]
  readonly filtered: boolean
  readonly onReset: () => void
  readonly onAnswer: (task: CatalogTask) => void
}

function Results({ tasks, filtered, onReset, onAnswer }: ResultsProps) {
  const { t } = useTranslation("tasks")
  if (tasks.length === 0)
    return (
      <EmptyState
        icon="task"
        title={t(filtered ? "empty.filteredTitle" : "empty.title")}
        description={t(filtered ? "empty.filteredText" : "empty.text")}
        action={
          filtered ? (
            <Button variant="secondary" icon="refresh" onClick={onReset}>
              {t("filters.reset")}
            </Button>
          ) : undefined
        }
      />
    )
  return (
    <div className={styles.grid}>
      {tasks.map((task, index) => (
        <TaskCard key={task.id} task={task} index={index} onAnswer={onAnswer} />
      ))}
    </div>
  )
}

export function TaskCatalog() {
  const { t } = useTranslation("tasks")
  const [grade, setGrade] = useState(ALL)
  const [topic, setTopic] = useState(ALL)
  const [answering, setAnswering] = useState<CatalogTask | null>(null)
  const gradeOptions = useGradeOptions()
  const topicOptions = useTopicOptions()
  const catalog = useTaskCatalog({
    grade: grade === ALL ? null : grade,
    topic: topic === ALL ? null : topic,
  })
  const filtered = grade !== ALL || topic !== ALL
  const reset = () => {
    setGrade(ALL)
    setTopic(ALL)
  }
  return (
    <div className={styles.catalog}>
      <div className={styles.filters}>
        <Select
          label={t("filters.grade")}
          value={grade}
          onChange={setGrade}
          options={gradeOptions}
        />
        <Select
          label={t("filters.topic")}
          value={topic}
          onChange={setTopic}
          options={topicOptions}
        />
      </div>
      <div className={styles.results} data-stale={catalog.isPlaceholderData}>
        {catalog.isError ? (
          <LoadError
            error={catalog.error}
            onRetry={() => void catalog.refetch()}
            pending={catalog.isFetching}
          />
        ) : catalog.data === undefined ? (
          <Skeleton shape="block" />
        ) : (
          <Results
            tasks={catalog.data.filter((task) => !task.answered)}
            filtered={filtered}
            onReset={reset}
            onAnswer={setAnswering}
          />
        )}
      </div>
      <AnswerDrawer task={answering} onClose={() => setAnswering(null)} />
    </div>
  )
}
