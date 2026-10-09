import { useNavigate } from "react-router"
import { useCompany } from "@/entities/company"
import { CompanyEditor } from "@/features/company-profile"
import type { Company } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Banner, LoadError, PageBody, PageHeader, Skeleton, toast } from "@/shared/ui"

export function EmployerCompanyPage() {
  const { t } = useTranslation("company")
  const navigate = useNavigate()
  const company = useCompany()
  useDocumentTitle(t("title"))

  const onSaved = (_saved: Company, created: boolean) => {
    if (!created) return void toast.success(t("toast.saved"))
    toast.success(t("toast.created"), {
      label: t("toast.toVacancies"),
      onAction: () => navigate("/employer/vacancies", { viewTransition: true }),
    })
  }

  const body = () => {
    if (company.isError)
      return (
        <LoadError
          error={company.error}
          onRetry={() => void company.refetch()}
          pending={company.isFetching}
        />
      )
    if (company.data === undefined) return <Skeleton shape="block" />
    return <CompanyEditor company={company.data} onSaved={onSaved} />
  }

  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} />
      <PageBody>
        {company.data === null ? <Banner tone="info" icon="company" title={t("missing")} /> : null}
        {body()}
      </PageBody>
    </>
  )
}
