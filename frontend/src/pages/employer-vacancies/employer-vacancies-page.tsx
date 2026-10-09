import { useState } from "react"
import { useSearchParams } from "react-router"
import { useCompany } from "@/entities/company"
import { useOwnVacancies } from "@/entities/vacancy"
import { VacancyDrawer } from "@/features/vacancy-editor"
import type { Vacancy } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Button, PageBody, PageHeader, Tabs } from "@/shared/ui"
import { isShown, VacancyGrid, type VacancyTab } from "./vacancy-grid/vacancy-grid"

interface Editing {
  readonly session: number
  readonly open: boolean
  readonly vacancy: Vacancy | null
}

export function EmployerVacanciesPage() {
  const { t } = useTranslation("vacancyEditor")
  const [params, setParams] = useSearchParams()
  const vacancies = useOwnVacancies()
  const company = useCompany()
  const [editing, setEditing] = useState<Editing>({ session: 0, open: false, vacancy: null })
  useDocumentTitle(t("title"))
  const tab: VacancyTab = params.get("tab") === "archived" ? "archived" : "published"
  const count = (value: VacancyTab) =>
    (vacancies.data ?? []).filter((vacancy) => isShown(vacancy, value)).length
  const edit = (vacancy: Vacancy | null) =>
    setEditing((current) => ({ session: current.session + 1, open: true, vacancy }))
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
        <Tabs<VacancyTab>
          label={t("title")}
          value={tab}
          onChange={(next) => setParams(next === "archived" ? { tab: next } : {})}
          tabs={[
            {
              value: "published",
              label: t("tabs.published"),
              icon: "vacancy",
              count: count("published"),
            },
            {
              value: "archived",
              label: t("tabs.archived"),
              icon: "revoked",
              count: count("archived"),
            },
          ]}
        >
          <VacancyGrid tab={tab} noCompany={noCompany} create={create} onEdit={edit} />
        </Tabs>
        <VacancyDrawer
          key={editing.session}
          open={editing.open}
          vacancy={editing.vacancy}
          onClose={() => setEditing((current) => ({ ...current, open: false }))}
        />
      </PageBody>
    </>
  )
}
