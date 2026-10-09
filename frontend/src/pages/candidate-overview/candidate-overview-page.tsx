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
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { LoadError, PageBody, PageHeader, Skeleton } from "@/shared/ui"
import styles from "./candidate-overview-page.module.css"

function OverviewSkeleton() {
  return (
    <div className={styles.grid} aria-hidden="true">
      <div className={styles.side}>
        <Skeleton shape="block" className={styles.placeholder} />
      </div>
      <div className={styles.main}>
        <Skeleton shape="block" className={styles.placeholder} />
      </div>
      <div className={styles.aside}>
        <Skeleton shape="block" className={styles.placeholder} />
      </div>
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
            <div className={styles.side}>
              <CategoryPanel path={data} motionIndex={0} />
              {data.history.length === 0 ? null : (
                <HistoryPanel history={data.history} motionIndex={4} className={styles.history} />
              )}
            </div>
            <div className={styles.main}>
              {level === null ? null : (
                <SkillPanel
                  profile={level}
                  fspLinked={fsp.data?.linked ?? null}
                  motionIndex={1}
                  className={styles.skills}
                />
              )}
            </div>
            <div className={styles.aside}>
              <FeedbackPanel motionIndex={2} className={styles.feedback} />
              <InvitationsPanel motionIndex={3} className={styles.invitations} />
              <ProfilePanel motionIndex={5} className={styles.profile} />
            </div>
          </div>
        )}
      </PageBody>
    </>
  )
}
