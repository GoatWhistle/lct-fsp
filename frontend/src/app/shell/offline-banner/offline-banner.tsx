import { useOnline } from "@/shared/hooks"
import { useTranslation } from "@/shared/i18n"
import { Banner } from "@/shared/ui"
import styles from "./offline-banner.module.css"

export function OfflineBanner() {
  const { t } = useTranslation()
  const online = useOnline()
  return (
    <div className={styles.slot} aria-live="polite">
      <Banner tone="attention" icon="offline" title={t("shell.offline")} open={!online} />
    </div>
  )
}
