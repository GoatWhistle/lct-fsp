import { useNeeds } from "@/entities/need"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { NeedRow } from "../need-row/need-row"
import styles from "./need-list.module.css"

export function NeedList() {
  const { t } = useTranslation("need")
  const needs = useNeeds()
  if (needs.isError)
    return (
      <LoadError
        error={needs.error}
        onRetry={() => void needs.refetch()}
        pending={needs.isFetching}
      />
    )
  if (needs.data === undefined) return <Skeleton lines={6} />
  if (needs.data.length === 0)
    return (
      <EmptyState
        size="hero"
        icon="need"
        title={t("list.emptyTitle")}
        description={t("list.emptyText")}
        action={
          <div className={styles.emptyActions}>
            <ButtonLink to="/employer/needs/new" icon="plus">
              {t("list.new")}
            </ButtonLink>
            <ButtonLink to="/employer/needs/text" variant="secondary" icon="llm">
              {t("list.fromText")}
            </ButtonLink>
          </div>
        }
      />
    )
  return (
    <ul className={styles.list}>
      {needs.data.map((need, index) => (
        <NeedRow key={need.id} need={need} index={index} />
      ))}
    </ul>
  )
}
