import type { ReactNode } from "react"
import { useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, IconLabel, type IconName } from "@/shared/ui"
import styles from "./save-bar.module.css"

export interface SaveBarProps {
  readonly dirty: boolean
  readonly created: boolean
  readonly saving: boolean
  readonly missing: number
  readonly onSave: () => void
  readonly onReset: () => void
  readonly extra?: ReactNode
  readonly className?: string | undefined
}

interface Status {
  readonly key: string
  readonly icon: IconName
  readonly tone: "danger" | "accent" | "secondary"
  readonly text: string
}

function useStatus({ dirty, created, missing }: SaveBarProps): Status {
  const { t } = useTranslation("profile")
  if (missing > 0)
    return {
      key: "missing",
      icon: "alert",
      tone: "danger",
      text: t("save.missing", { count: missing }),
    }
  if (dirty) return { key: "dirty", icon: "edit", tone: "accent", text: t("save.dirty") }
  if (!created) return { key: "new", icon: "pending", tone: "secondary", text: t("save.new") }
  return { key: "saved", icon: "check", tone: "secondary", text: t("save.saved") }
}

export function SaveBar(props: SaveBarProps) {
  const { t } = useTranslation("profile")
  const status = useStatus(props)
  return (
    <div className={props.className}>
      <div className={styles.bar}>
        <Swap swapKey={status.key} as="div" className={styles.status}>
          <IconLabel icon={status.icon} tone={status.tone}>
            {status.text}
          </IconLabel>
        </Swap>
        <div className={styles.actions}>
          {props.extra}
          {props.dirty ? (
            <Button
              variant="ghost"
              icon="retry"
              disabled={props.saving}
              className={styles.reset}
              onClick={props.onReset}
            >
              {t("save.reset")}
            </Button>
          ) : null}
          <Button
            icon="check"
            disabled={props.created && !props.dirty}
            pending={props.saving}
            pendingLabel={t("save.saving")}
            onClick={props.onSave}
          >
            {t("save.action")}
          </Button>
        </div>
      </div>
    </div>
  )
}
