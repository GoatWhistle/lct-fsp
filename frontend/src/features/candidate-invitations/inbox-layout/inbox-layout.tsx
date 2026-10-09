import type { ReactNode } from "react"
import { useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { ButtonLink, Card, ScrollArea } from "@/shared/ui"
import styles from "./inbox-layout.module.css"

export interface InboxLayoutProps {
  readonly label: string
  readonly list: ReactNode
  readonly detail: ReactNode
  readonly selectedKey: string | null
  readonly backTo: string
}

export function InboxLayout({ label, list, detail, selectedKey, backTo }: InboxLayoutProps) {
  const { t } = useTranslation("invitations")
  return (
    <div className={styles.layout} data-selected={selectedKey !== null}>
      <Card as="div" className={styles.list}>
        <ScrollArea label={label} surface="card" className={styles.scroll}>
          {list}
        </ScrollArea>
      </Card>
      <div className={styles.detail}>
        <ButtonLink
          to={backTo}
          variant="ghost"
          size="compact"
          icon="arrow-left"
          className={styles.back}
        >
          {t("back")}
        </ButtonLink>
        <Swap swapKey={selectedKey ?? "none"} as="div">
          {detail}
        </Swap>
      </div>
    </div>
  )
}
