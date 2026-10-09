import { useState } from "react"
import { MatchScore } from "@/entities/measure"
import { anonymousId, useShortlist } from "@/entities/selection"
import { useTranslation } from "@/shared/i18n"
import { Button, Checkbox, Dialog, EmptyState, Skeleton } from "@/shared/ui"
import { CompareDialog } from "../compare-dialog/compare-dialog"
import styles from "./shortlist-drawer.module.css"

const COMPARE_LIMIT = 3

export interface ShortlistDrawerProps {
  readonly selectionId: string
  readonly stackCap: number
  readonly open: boolean
  readonly onClose: () => void
  readonly onPick: (id: string) => void
}

export function ShortlistDrawer({
  selectionId,
  stackCap,
  open,
  onClose,
  onPick,
}: ShortlistDrawerProps) {
  const { t } = useTranslation("selection")
  const shortlist = useShortlist(selectionId)
  const [picked, setPicked] = useState<readonly string[]>([])
  const [comparing, setComparing] = useState(false)
  const entries = shortlist.data?.entries ?? []
  const chosen = entries.filter((entry) => picked.includes(entry.candidate_id))
  const toggle = (id: string, on: boolean) =>
    setPicked((current) => (on ? [...current, id] : current.filter((item) => item !== id)))

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        size="drawer"
        title={t("shortlist.title")}
        description={t("shortlist.lead")}
        actions={
          entries.length === 0 ? undefined : (
            <Button icon="sort" disabled={chosen.length < 2} onClick={() => setComparing(true)}>
              {t("shortlist.compare")}
            </Button>
          )
        }
      >
        {shortlist.data === undefined ? (
          <Skeleton lines={4} />
        ) : entries.length === 0 ? (
          <EmptyState
            icon="star"
            title={t("shortlist.emptyTitle")}
            description={t("shortlist.empty")}
          />
        ) : (
          <ul className={styles.list}>
            {entries.map((entry) => {
              const id = anonymousId(entry.candidate_id)
              const on = picked.includes(entry.candidate_id)
              return (
                <li key={entry.candidate_id} className={styles.item}>
                  <Checkbox
                    label={<span className="visually-hidden">{t("shortlist.pick", { id })}</span>}
                    checked={on}
                    disabled={!on && picked.length >= COMPARE_LIMIT}
                    onChange={(value) => toggle(entry.candidate_id, value)}
                  />
                  <Button
                    variant="link"
                    className={styles.id}
                    onClick={() => onPick(entry.candidate_id)}
                  >
                    {id}
                  </Button>
                  {entry.match_score === null ? null : (
                    <MatchScore
                      score={entry.match_score}
                      topics={entry.topics}
                      stack={entry.stack}
                      stackCap={stackCap}
                      size="sm"
                    />
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {picked.length >= COMPARE_LIMIT ? (
          <p className={styles.limit}>{t("shortlist.limit")}</p>
        ) : null}
      </Dialog>
      <CompareDialog open={comparing} onClose={() => setComparing(false)} entries={chosen} />
    </>
  )
}
