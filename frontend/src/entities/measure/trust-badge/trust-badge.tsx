import { useTranslation } from "@/shared/i18n"
import type { IconName } from "@/shared/ui"
import { Icon } from "@/shared/ui"
import styles from "./trust-badge.module.css"

export type TrustSource = "fsp" | "verification" | "test" | "regular_task" | "self"

const TRUST_ICON: Readonly<Record<TrustSource, IconName>> = {
  fsp: "fsp",
  verification: "verification",
  test: "test",
  regular_task: "task",
  self: "self-report",
}

export interface TrustBadgeProps {
  readonly source: TrustSource
  readonly label?: string | undefined
}

export function TrustBadge({ source, label }: TrustBadgeProps) {
  const { t } = useTranslation("measure")
  return (
    <span className={styles.badge} data-source={source}>
      <Icon name={TRUST_ICON[source]} size="sm" />
      {label ?? t(`trust.${source}`)}
    </span>
  )
}
