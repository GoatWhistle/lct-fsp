import { useTranslation } from "@/shared/i18n"
import { Skeleton } from "@/shared/ui"
import styles from "./route-fallback.module.css"

export function RouteFallback() {
  const { t } = useTranslation()
  return (
    <div className={styles.fallback} role="status" aria-label={t("state.loading")}>
      <Skeleton shape="line" lines={2} />
      <Skeleton shape="block" />
      <Skeleton shape="block" />
    </div>
  )
}
