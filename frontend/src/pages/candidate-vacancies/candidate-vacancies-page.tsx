import { useNavigate, useParams, useSearchParams } from "react-router"
import { isOpenStatus } from "@/entities/invitation"
import { useMyApplications } from "@/entities/vacancy"
import { ApplicationList, VacancyBoard } from "@/features/candidate-vacancies"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader, Tabs } from "@/shared/ui"

type Tab = "vacancies" | "applications"

export function CandidateVacanciesPage() {
  const { t } = useTranslation("vacancies")
  const { id } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const applications = useMyApplications()
  const tab: Tab =
    id === undefined && params.get("tab") === "applications" ? "applications" : "vacancies"
  useDocumentTitle(t("title"))
  const waiting = applications.data?.filter(
    (item) => isOpenStatus(item.status) && item.revoked_at === null,
  ).length
  const change = (next: Tab) =>
    navigate(
      next === "applications" ? "/candidate/vacancies?tab=applications" : "/candidate/vacancies",
    )
  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} />
      <PageBody>
        <Tabs<Tab>
          label={t("title")}
          value={tab}
          onChange={change}
          tabs={[
            { value: "vacancies", label: t("tabs.vacancies"), icon: "vacancy" },
            {
              value: "applications",
              label: t("tabs.applications"),
              icon: "application",
              count: waiting === 0 ? undefined : waiting,
            },
          ]}
        >
          {tab === "vacancies" ? <VacancyBoard selectedId={id ?? null} /> : <ApplicationList />}
        </Tabs>
      </PageBody>
    </>
  )
}
