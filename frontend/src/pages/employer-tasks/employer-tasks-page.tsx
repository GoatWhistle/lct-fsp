import { useState } from "react"
import { useSearchParams } from "react-router"
import { useCompany } from "@/entities/company"
import { useAwaitingReview, useOwnTasks } from "@/entities/task"
import { TaskDrawer } from "@/features/task-editor"
import type { RegularTask } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Button, LoadError, PageBody, PageHeader, Skeleton, Tabs } from "@/shared/ui"
import { type TaskFilter, TaskGrid } from "./task-grid/task-grid"

const FILTERS: readonly TaskFilter[] = ["active", "review", "withdrawn"]

const FILTER_ICON = { active: "task", review: "pending", withdrawn: "revoked" } as const

interface Editing {
  readonly session: number
  readonly open: boolean
  readonly task: RegularTask | null
}

function isFilter(value: string | null): value is TaskFilter {
  return FILTERS.some((item) => item === value)
}

export function EmployerTasksPage() {
  const { t } = useTranslation("taskEditor")
  const [params, setParams] = useSearchParams()
  const tasks = useOwnTasks()
  const awaiting = useAwaitingReview(tasks.data)
  const company = useCompany()
  const [editing, setEditing] = useState<Editing>({ session: 0, open: false, task: null })
  useDocumentTitle(t("title"))
  const raw = params.get("filter")
  const filter: TaskFilter = isFilter(raw) ? raw : "active"
  const matches: Record<TaskFilter, (task: RegularTask) => boolean> = {
    active: (task) => task.withdrawn_at === null,
    review: (task) => awaiting.has(task.id),
    withdrawn: (task) => task.withdrawn_at !== null,
  }
  const all = tasks.data ?? []
  const edit = (task: RegularTask | null) =>
    setEditing((current) => ({ session: current.session + 1, open: true, task }))
  const noCompany = company.data === null
  const create = (
    <Button
      icon="plus"
      onClick={() => edit(null)}
      disabled={noCompany}
      disabledReason={noCompany ? t("needCompany") : undefined}
    >
      {t("create")}
    </Button>
  )
  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} actions={create} />
      <PageBody>
        <Tabs<TaskFilter>
          label={t("filter.label")}
          value={filter}
          onChange={(next) => setParams(next === "active" ? {} : { filter: next })}
          tabs={FILTERS.map((value) => {
            const count = all.filter(matches[value]).length
            return {
              value,
              label: t(`filter.${value}`),
              icon: FILTER_ICON[value],
              count: count === 0 ? undefined : count,
            }
          })}
        >
          {tasks.isError ? (
            <LoadError
              error={tasks.error}
              onRetry={() => void tasks.refetch()}
              pending={tasks.isFetching}
            />
          ) : tasks.data === undefined ? (
            <Skeleton shape="block" />
          ) : (
            <TaskGrid
              tasks={all.filter(matches[filter])}
              filter={filter}
              awaiting={awaiting}
              noCompany={noCompany}
              create={create}
              onEdit={edit}
            />
          )}
        </Tabs>
        <TaskDrawer
          key={editing.session}
          open={editing.open}
          task={editing.task}
          onClose={() => setEditing((current) => ({ ...current, open: false }))}
        />
      </PageBody>
    </>
  )
}
