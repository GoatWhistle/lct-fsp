import { Navigate } from "react-router"
import { usePath } from "@/entities/candidate-path"
import { useFspStatus } from "@/entities/profile"
import {
  CategoryPanel,
  FeedbackPanel,
  HistoryPanel,
  InvitationsPanel,
  ProfilePanel,
  SkillPanel,
} from "@/features/candidate-overview"
import { VerificationCard } from "@/features/test-verification"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { LoadError, PageBody, PageHeader, Skeleton } from "@/shared/ui"
import styles from "./candidate-overview-page.module.css"

function OverviewSkeleton() {
  return (
    <div className={styles.grid} aria-hidden="true">
      <Skeleton shape="block" className={styles.hero} />
      <Skeleton shape="block" className={styles.placeholder} />
      <Skeleton shape="block" className={styles.placeholder} />
    </div>
  )
}

export function CandidateOverviewPage() {
  const { t } = useTranslation("overview")
  const path = usePath()
  const fsp = useFspStatus()
  useDocumentTitle(t("title"))
  const data = path.data
  if (data !== undefined && (data.category === null || data.topic_block !== null))
    return <Navigate to="/candidate/path" replace />
  const level = data?.profile ?? null
  return (
    <>
      <PageHeader title={t("title")} />
      <PageBody>
        {path.isError ? (
          <LoadError
            error={path.error}
            onRetry={() => void path.refetch()}
            pending={path.isFetching}
          />
        ) : data === undefined ? (
          <OverviewSkeleton />
        ) : (
          <div className={styles.grid}>
            <CategoryPanel path={data} motionIndex={0} className={styles.hero} />
            <div className={styles.main}>
              {level === null ? null : (
                <SkillPanel profile={level} fspLinked={fsp.data?.linked ?? null} motionIndex={1} />
              )}
            </div>
            <div className={styles.aside}>
              <VerificationCard path={data} />
              <FeedbackPanel motionIndex={2} />
              <InvitationsPanel motionIndex={3} />
              {data.history.length === 0 ? null : (
                <HistoryPanel history={data.history} motionIndex={4} />
              )}
              <ProfilePanel motionIndex={5} />
            </div>
          </div>
        )}
      </PageBody>
    </>
  )
}
