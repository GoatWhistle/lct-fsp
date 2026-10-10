import { Navigate } from "react-router"
import { usePath } from "@/entities/candidate-path"
import {
  CategoryPanel,
  FeedbackButton,
  HistoryPanel,
  InvitationsPanel,
  NextSteps,
  ProfilePanel,
  SkillPanel,
} from "@/features/candidate-overview"
import { VerificationCard } from "@/features/test-verification"
import type { CandidatePath } from "@/shared/api"
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

function TopicBlockBanner({ path }: { readonly path: CandidatePath }) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const block = path.topic_block
  if (block === null) return null
  return (
    <Banner
      tone="info"
      icon="test"
      title={t("block.open", {
        topic: names.topic(block.topic),
        answered: block.answered,
        items: block.items,
      })}
      action={
        <ButtonLink to="/candidate/test" size="compact" icon="arrow-right" iconPosition="end">
          {t("block.continue")}
        </ButtonLink>
      }
      className={styles.wide}
    />
  )
}

export function CandidateOverviewPage() {
  const { t } = useTranslation("overview")
  const path = usePath()
  useDocumentTitle(t("title"))
  const data = path.data
  if (data !== undefined && data.category === null) return <Navigate to="/candidate/path" replace />
  const level = data?.profile ?? null
  return (
    <>
      <PageHeader title={t("title")} actions={<FeedbackButton />} />
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
            <TopicBlockBanner path={data} />
            <CategoryPanel path={data} motionIndex={0} className={styles.wide} />
            <div className={styles.top}>
              <NextSteps motionIndex={1} />
              <VerificationCard path={data} />
              <InvitationsPanel motionIndex={2} />
            </div>
            {level === null ? null : (
              <SkillPanel profile={level} motionIndex={3} className={styles.skills} />
            )}
            <div className={styles.bottom}>
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
