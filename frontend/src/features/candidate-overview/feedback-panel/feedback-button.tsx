import { useId, useRef, useState } from "react"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Button, Card, CloseButton, Popover, ScrollArea } from "@/shared/ui"
import styles from "./feedback-button.module.css"
import { FeedbackContent, useHints } from "./feedback-panel"

export function FeedbackButton() {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  const id = useId()
  const hints = useHints()
  if (hints.length === 0) return null
  return (
    <span className={styles.trigger}>
      <Button
        ref={anchor}
        variant="secondary"
        icon="match"
        className={styles.button}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-haspopup="dialog"
        onClick={() => setOpen(!open)}
      >
        {t("feedback.open")}
      </Button>
      <span className={styles.count} aria-hidden="true">
        {format.integer(hints.length)}
      </span>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={anchor}
        placement="bottom-end"
        id={id}
        className={styles.popover}
      >
        <ScrollArea label={t("feedback.title")} className={styles.scroll}>
          <Card
            as="div"
            role="dialog"
            title={t("feedback.title")}
            description={t("feedback.lead")}
            actions={<CloseButton onClick={() => setOpen(false)} />}
            className={styles.panel}
          >
            <FeedbackContent />
          </Card>
        </ScrollArea>
      </Popover>
    </span>
  )
}
