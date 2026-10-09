import { useRef, useState } from "react"
import type { Selection, SelectionBlock } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, Popover, Switch } from "@/shared/ui"
import { BLOCKS } from "../selection-model"
import styles from "./selection-bar.module.css"

export interface SelectionBarProps {
  readonly selection: Selection
  readonly shortlistCount: number
  readonly matchOnly: boolean
  readonly onMatchOnly: (value: boolean) => void
  readonly onOpenShortlist: () => void
}

function counts(selection: Selection, block: SelectionBlock): readonly [number, number] {
  if (block === "exact") return [selection.filtered_exact_total, selection.exact_total]
  if (block === "nearby") return [selection.filtered_nearby_total, selection.nearby_total]
  return [selection.filtered_unconfirmed_total, selection.unconfirmed_total]
}

function Method({ stackCap }: { readonly stackCap: number }) {
  const { t } = useTranslation("selection")
  const format = useFormatters()
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement | null>(null)
  return (
    <>
      <Button
        ref={anchor}
        variant="ghost"
        size="compact"
        icon="info"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {t("method.open")}
      </Button>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={anchor}
        className={styles.method}
      >
        <p className={styles.methodTitle}>{t("method.title")}</p>
        <ol className={styles.points}>
          <li>{t("method.match", { cap: format.percent(stackCap) })}</li>
          <li>{t("method.place")}</li>
          <li>{t("method.category")}</li>
        </ol>
      </Popover>
    </>
  )
}

export function SelectionBar({
  selection,
  shortlistCount,
  matchOnly,
  onMatchOnly,
  onOpenShortlist,
}: SelectionBarProps) {
  const { t } = useTranslation("selection")
  return (
    <div className={styles.bar}>
      <dl className={styles.counts} aria-label={t("counts.label")}>
        {BLOCKS.map((block) => {
          const [shown, total] = counts(selection, block)
          return (
            <div key={block} className={styles.count} data-block={block}>
              <dt className={styles.countLabel}>{t(`selection:counts.${block}` as never)}</dt>
              <dd className={styles.countValue}>
                <Swap swapKey={`${shown}-${total}`}>
                  {shown === total ? total : t("counts.of", { shown, total })}
                </Swap>
              </dd>
            </div>
          )
        })}
      </dl>
      <div className={styles.tools}>
        <Switch label={t("order.matchOnly")} checked={matchOnly} onChange={onMatchOnly} />
        <Method stackCap={selection.stack_cap} />
        <Button variant="secondary" size="compact" icon="star" onClick={onOpenShortlist}>
          {t("shortlist.open")}
          <span className={styles.badge}>
            <Swap swapKey={shortlistCount}>{shortlistCount}</Swap>
          </span>
        </Button>
      </div>
    </div>
  )
}
