import { Navigate } from "react-router"
import { usePath } from "@/entities/candidate-path"
import { useFspStatus } from "@/entities/profile"
import {
  CategoryPanel,
  HistoryPanel,
  InvitationsPanel,
  ProfilePanel,
  SkillPanel,
} from "@/features/candidate-overview"
import { VerificationCard } from "@/features/test-verification"
import { useCatalogNames, useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Banner, ButtonLink, LoadError, PageBody, PageHeader, Skeleton } from "@/shared/ui"
import styles from "./candidate-overview-page.module.css"

function OverviewSkeleton() {
  return (
    <div className={styles.grid} aria-hidden="true">
      <Skeleton shape="block" className={styles.wide} />
      <Skeleton shape="block" className={styles.placeholder} />
      <Skeleton shape="block" className={styles.placeholder} />
    </div>
  )
}

export function CandidateOverviewPage() {
  const { t } = useTranslation("overview")
  const path = usePath()
  const fsp = useFspStatus()
  const names = useCatalogNames()
  useDocumentTitle(t("title"))
  const data = path.data
  if (data !== undefined && data.category === null) return <Navigate to="/candidate/path" replace />
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
            {data.topic_block === null ? null : (
              <Banner
                tone="info"
                icon="test"
                title={t("block.open", {
                  topic: names.topic(data.topic_block.topic),
                  answered: data.topic_block.answered,
                  items: data.topic_block.items,
                })}
                action={
                  <ButtonLink
                    to="/candidate/test"
                    size="compact"
                    icon="arrow-right"
                    iconPosition="end"
                  >
                    {t("block.continue")}
                  </ButtonLink>
                }
                className={styles.wide}
              />
            )}
            <CategoryPanel path={data} motionIndex={0} className={styles.wide} />
            <div className={styles.column}>
              {level === null ? null : (
                <SkillPanel profile={level} fspLinked={fsp.data?.linked ?? null} motionIndex={1} />
              )}
            </div>
            <div className={styles.column}>
              <VerificationCard path={data} />
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
