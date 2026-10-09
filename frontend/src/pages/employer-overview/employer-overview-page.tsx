import { useCompany } from "@/entities/company"
import { useSession } from "@/entities/session"
import {
  ActivityPanel,
  AttentionPanel,
  CompanyTask,
  MetricsRow,
  NeedsPanel,
} from "@/features/employer-overview"
import { NeedText } from "@/features/need-text"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { ButtonLink, LoadError, PageBody, PageHeader, Section, Skeleton } from "@/shared/ui"
import styles from "./employer-overview-page.module.css"

function Headline() {
  const company = useCompany()
  if (company.isError)
    return (
      <LoadError
        error={company.error}
        onRetry={() => void company.refetch()}
        pending={company.isFetching}
      />
    )
  if (company.data === undefined) return <Skeleton shape="block" />
  return company.data === null ? <CompanyTask /> : <MetricsRow />
}

export function EmployerOverviewPage() {
  const { t } = useTranslation("employer")
  const company = useCompany()
  const session = useSession()
  useDocumentTitle(t("overview.title"))
  return (
    <>
      <PageHeader
        title={t("overview.title")}
        description={company.data?.name}
        actions={
          <ButtonLink to="/employer/needs/new" icon="plus">
            {t("overview.newNeed")}
          </ButtonLink>
        }
      />
      <PageBody>
        {session.data?.demo ? (
          <Section title={t("overview.jury.title")} lead={t("overview.jury.lead")}>
            <NeedText />
          </Section>
        ) : null}
        <Headline />
        <div className={styles.grid}>
          <NeedsPanel />
          <div className={styles.side}>
            <ActivityPanel />
            <AttentionPanel />
          </div>
        </div>
      </PageBody>
    </>
  )
}
