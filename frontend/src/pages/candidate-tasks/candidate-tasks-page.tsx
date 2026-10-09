import { useNavigate, useSearchParams } from "react-router"
import { usePath } from "@/entities/candidate-path"
import { useMyAnswers } from "@/entities/task"
import { CategoryGate } from "@/features/candidate-overview"
import { AnswerList, TaskCatalog } from "@/features/candidate-tasks"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader, Tabs } from "@/shared/ui"

type Tab = "catalog" | "answers"

export function CandidateTasksPage() {
  const { t } = useTranslation("tasks")
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const path = usePath()
  const answers = useMyAnswers(path.data?.category != null)
  const tab: Tab = params.get("tab") === "answers" ? "answers" : "catalog"
  useDocumentTitle(t("title"))
  const waiting = answers.data?.filter((item) => item.status === "awaiting_review").length
  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} />
      <PageBody>
        <CategoryGate topic="tasks">
          <Tabs<Tab>
            label={t("title")}
            value={tab}
            onChange={(next) =>
              navigate(next === "answers" ? "/candidate/tasks?tab=answers" : "/candidate/tasks")
            }
            tabs={[
              { value: "catalog", label: t("tabs.catalog"), icon: "task" },
              {
                value: "answers",
                label: t("tabs.answers"),
                icon: "application",
                count: waiting === 0 ? undefined : waiting,
              },
            ]}
          >
            {tab === "catalog" ? <TaskCatalog /> : <AnswerList />}
          </Tabs>
        </CategoryGate>
      </PageBody>
    </>
  )
}
