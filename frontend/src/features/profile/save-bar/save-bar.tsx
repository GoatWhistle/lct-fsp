import { useTranslation } from "@/shared/i18n"
import { usePresence } from "@/shared/motion"
import { Button, IconLabel } from "@/shared/ui"
import styles from "./save-bar.module.css"

export interface SaveBarProps {
  readonly open: boolean
  readonly saving: boolean
  readonly missing: number
  readonly onSave: () => void
  readonly onReset: () => void
}

export function SaveBar({ open, saving, missing, onSave, onReset }: SaveBarProps) {
  const { t } = useTranslation("profile")
  const presence = usePresence(open)
  if (!presence.mounted) return null
  return (
    <div
      className={styles.bar}
      data-state={presence.state}
      data-motion="fade"
      onAnimationEnd={presence.onAnimationEnd}
    >
      <div className={styles.panel} data-surface="inverse">
        <IconLabel
          icon={missing > 0 ? "alert" : "edit"}
          tone={missing > 0 ? "danger" : "default"}
          className={styles.note}
        >
          {missing > 0 ? t("save.missing", { count: missing }) : t("save.dirty")}
        </IconLabel>
        <div className={styles.actions}>
          <Button variant="ghost" icon="close" onClick={onReset} disabled={saving}>
            {t("save.reset")}
          </Button>
          <Button icon="check" pending={saving} pendingLabel={t("save.saving")} onClick={onSave}>
            {t("save.action")}
          </Button>
        </div>
      </div>
    </div>
  )
}
