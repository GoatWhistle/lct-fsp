import { GradeRuler } from "@/entities/measure"
import { anonymousId } from "@/entities/selection"
import type { SelectionEntry } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { Dialog, NoValue, ScrollArea } from "@/shared/ui"
import { levelOf } from "../selection-model"
import styles from "./compare-dialog.module.css"

export interface CompareDialogProps {
  readonly open: boolean
  readonly onClose: () => void
  readonly entries: readonly SelectionEntry[]
}

export function CompareDialog({ open, onClose, entries }: CompareDialogProps) {
  const { t } = useTranslation("selection")
  const names = useCatalogNames()
  const format = useFormatters()
  const topics = entries[0]?.topics ?? []
  return (
    <Dialog open={open} onClose={onClose} size="wide" title={t("compare.title")}>
      <ScrollArea label={t("compare.title")}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{t("compare.topic")}</th>
              {entries.map((entry) => (
                <th key={entry.candidate_id} scope="col" className={styles.candidate}>
                  {anonymousId(entry.candidate_id)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">{t("compare.match")}</th>
              {entries.map((entry) => (
                <td key={entry.candidate_id} className={styles.score}>
                  {entry.match_score === null ? <NoValue /> : format.percent(entry.match_score)}
                </td>
              ))}
            </tr>
            {topics.map((topic) => (
              <tr key={topic.topic.code}>
                <th scope="row">{names.topic(topic.topic)}</th>
                {entries.map((entry) => {
                  const fit = entry.topics.find((item) => item.topic.code === topic.topic.code)
                  return (
                    <td key={entry.candidate_id}>
                      {fit === undefined ? (
                        <NoValue />
                      ) : (
                        <GradeRuler
                          level={levelOf(fit)}
                          size="inline"
                          required={fit.requirement}
                          caption={false}
                        />
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollArea>
    </Dialog>
  )
}
