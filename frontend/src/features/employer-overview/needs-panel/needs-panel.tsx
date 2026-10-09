import { useNeeds } from "@/entities/need"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { NeedRow } from "../need-row/need-row"
import styles from "./needs-panel.module.css"

const SHOWN = 5

export interface NeedsPanelProps {
  readonly className?: string | undefined
}

function NeedsBody() {
  const { t } = useTranslation("employer")
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
        icon="need"
        title={t("overview.needs.emptyTitle")}
        description={t("overview.needs.emptyText")}
        action={
          <ButtonLink to="/employer/needs/new" icon="plus">
            {t("overview.needs.create")}
          </ButtonLink>
        }
      />
    )
  return (
    <ul className={styles.list}>
      {needs.data.slice(0, SHOWN).map((need, index) => (
        <NeedRow key={need.id} need={need} index={index} />
      ))}
    </ul>
  )
}

export function NeedsPanel({ className }: NeedsPanelProps) {
  const { t } = useTranslation("employer")
  return (
    <Card
      title={t("overview.needs.title")}
      className={className}
      motionIndex={1}
      actions={
        <ButtonLink to="/employer/needs" variant="ghost" size="compact" icon="need">
          {t("overview.needs.all")}
        </ButtonLink>
      }
    >
      <NeedsBody />
    </Card>
  )
}
