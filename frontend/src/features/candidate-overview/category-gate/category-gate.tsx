import type { ReactNode } from "react"
import { usePath } from "@/entities/candidate-path"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import styles from "./category-gate.module.css"

export type GateTopic = "invitations" | "tasks"

export interface CategoryGateProps {
  readonly topic: GateTopic
  readonly children: ReactNode
}

export function CategoryGate({ topic, children }: CategoryGateProps) {
  const { t } = useTranslation("overview")
  const path = usePath()
  if (path.isError)
    return (
      <LoadError error={path.error} onRetry={() => void path.refetch()} pending={path.isFetching} />
    )
  if (path.data === undefined) return <Skeleton shape="block" />
  if (path.data.category !== null) return children
  return (
    <div className={styles.gate}>
      <EmptyState
        size="hero"
        icon={topic === "invitations" ? "invitation" : "task"}
        title={t(`gate.${topic}.title`)}
        description={t(`gate.${topic}.text`)}
        action={
          <ButtonLink to="/candidate/path" icon="arrow-right" iconPosition="end">
            {t("gate.action")}
          </ButtonLink>
        }
      />
    </div>
  )
}
