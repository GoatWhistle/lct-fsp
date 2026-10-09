import { useNavigate, useSearchParams } from "react-router"
import { useApplications } from "@/entities/application"
import { ApplicationDetail, ApplicationList } from "@/features/applications"
import { useTranslation } from "@/shared/i18n"
import { Card, Chip, EmptyState, IconLabel, LoadError, Skeleton } from "@/shared/ui"
import { Inbox } from "../inbox/inbox"
import styles from "./applications-tab.module.css"

function linkWith(params: URLSearchParams, patch: Record<string, string | null>): string {
  const next = new URLSearchParams(params)
  next.set("tab", "applications")
  for (const [key, value] of Object.entries(patch)) {
    if (value === null) next.delete(key)
    else next.set(key, value)
  }
  return `/employer/invitations?${next.toString()}`
}

export function ApplicationsTab() {
  const { t } = useTranslation("applications")
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const applications = useApplications()
  const selectedId = params.get("application")
  const vacancyId = params.get("vacancy")
  if (applications.isError)
    return (
      <LoadError
        error={applications.error}
        onRetry={() => void applications.refetch()}
        pending={applications.isFetching}
      />
    )
  if (applications.data === undefined) return <Skeleton shape="block" />
  const shown =
    vacancyId === null
      ? applications.data
      : applications.data.filter((item) => item.vacancy_id === vacancyId)
  const selected = applications.data.find((item) => item.id === selectedId)
  const filterTitle = shown[0]?.vacancy_title
  return (
    <div className={styles.tab}>
      <div className={styles.toolbar}>
        <IconLabel icon="info" tone="secondary" size="sm">
          {t("hint")}
        </IconLabel>
        {vacancyId === null ? null : (
          <Chip
            icon="vacancy"
            tone="accent"
            removeLabel={t("clearFilter")}
            onRemove={() => navigate(linkWith(params, { vacancy: null }))}
          >
            {filterTitle ?? t("filtered")}
          </Chip>
        )}
      </div>
      <Inbox
        label={t("listLabel")}
        list={
          <ApplicationList
            applications={shown}
            selectedId={selectedId}
            linkTo={(id) => linkWith(params, { application: id })}
          />
        }
        detail={
          selected === undefined ? (
            <Card as="div">
              <EmptyState
                icon={selectedId === null ? "application" : "alert"}
                title={t(selectedId === null ? "pickTitle" : "missingTitle")}
                description={t(selectedId === null ? "pickText" : "missingText")}
              />
            </Card>
          ) : (
            <ApplicationDetail application={selected} />
          )
        }
        selectedKey={selectedId}
        backTo={linkWith(params, { application: null })}
      />
    </div>
  )
}
