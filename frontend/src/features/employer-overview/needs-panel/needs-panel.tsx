import { useState } from "react"
import { useNeeds } from "@/entities/need"
import { useTranslation } from "@/shared/i18n"
import { Button, ButtonLink, Card, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { NeedRow } from "../need-row/need-row"
import { latestByNeed, useRecentSelections } from "../recent-selections"
import styles from "./needs-panel.module.css"

const SHOWN = 5

export interface NeedsPanelProps {
  readonly className?: string | undefined
}

function NeedsBody() {
  const { t } = useTranslation("employer")
  const needs = useNeeds()
  const selections = useRecentSelections()
  const [expanded, setExpanded] = useState(false)
  const failed = needs.isError ? needs : selections.isError ? selections : null
  if (failed !== null)
    return (
      <LoadError
        error={failed.error}
        onRetry={() => void failed.refetch()}
        pending={failed.isFetching}
      />
    )
  if (needs.data === undefined || selections.data === undefined) return <Skeleton lines={5} />
  if (needs.data.length === 0)
    return (
      <EmptyState
        icon="need"
        title={t("overview.needs.emptyTitle")}
        description={t("overview.needs.emptyText")}
        action={
          <ButtonLink to="/employer/needs/text" icon="plus">
            {t("overview.needs.create")}
          </ButtonLink>
        }
      />
    )
  const latest = latestByNeed(selections.data)
  const hidden = needs.data.length - SHOWN
  const shown = expanded ? needs.data : needs.data.slice(0, SHOWN)
  return (
    <>
      <ul className={styles.list}>
        {shown.map((need, index) => (
          <NeedRow key={need.id} need={need} latest={latest.get(need.id)} index={index % SHOWN} />
        ))}
      </ul>
      {hidden > 0 ? (
        <Button
          variant="ghost"
          size="compact"
          icon={expanded ? "chevron-up" : "chevron-down"}
          className={styles.toggle}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded
            ? t("overview.needs.showLess")
            : t("overview.needs.showMore", { count: hidden })}
        </Button>
      ) : null}
    </>
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
