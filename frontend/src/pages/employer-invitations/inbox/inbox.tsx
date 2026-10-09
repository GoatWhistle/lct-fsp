import type { ReactNode } from "react"
import { useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { ButtonLink, Card, ScrollArea } from "@/shared/ui"
import styles from "./inbox.module.css"

export interface InboxProps {
  readonly label: string
  readonly list: ReactNode
  readonly detail: ReactNode
  readonly selectedKey: string | null
  readonly backTo: string
}

export function Inbox({ label, list, detail, selectedKey, backTo }: InboxProps) {
  const { t } = useTranslation("employer")
  return (
    <div className={styles.inbox} data-selected={selectedKey !== null}>
      <Card as="div" className={styles.listPane}>
        <ScrollArea label={label} surface="card" className={styles.scroll}>
          {list}
        </ScrollArea>
      </Card>
      <div className={styles.detailPane}>
        <ButtonLink
          to={backTo}
          variant="ghost"
          size="compact"
          icon="arrow-left"
          className={styles.back}
        >
          {t("invitations.back")}
        </ButtonLink>
        <Swap swapKey={selectedKey ?? "none"} as="div">
          {detail}
        </Swap>
      </div>
    </div>
  )
}
