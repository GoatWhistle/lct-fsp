import type { CandidateCard, FspAchievement, FspAnonymizedAchievement } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, Chip, Disclosure, IconLabel, type TermItem, Terms } from "@/shared/ui"
import styles from "./fsp-record.module.css"

export interface FspRecordProps {
  readonly card: CandidateCard
}

function Head({ item }: { readonly item: FspAnonymizedAchievement | FspAchievement }) {
  const { t } = useTranslation("catalog")
  const names = useCatalogNames()
  return (
    <div className={styles.head}>
      <Chip icon="fsp" tone="accent">
        {t(`catalog:fspResult.${item.result}` as never)}
      </Chip>
      <span className={styles.discipline}>{names.discipline(item.discipline)}</span>
      {"year" in item ? <span className={styles.year}>{item.year}</span> : null}
    </div>
  )
}

function Detailed({ items }: { readonly items: readonly FspAchievement[] }) {
  const { t } = useTranslation("card")
  const format = useFormatters()
  const terms = (item: FspAchievement): TermItem[] => [
    { key: "event", prose: true, label: t("fsp.event"), icon: "star", value: item.event },
    { key: "date", label: t("fsp.date"), icon: "calendar", value: format.date(item.date) },
    ...(item.place === null
      ? []
      : [
          { key: "place", label: t("fsp.place"), icon: "verification" as const, value: item.place },
        ]),
    ...(item.team_role === null
      ? []
      : [
          {
            key: "role",
            prose: true,
            label: t("fsp.role"),
            icon: "candidates" as const,
            value: item.team_role.name,
          },
        ]),
  ]
  return (
    <ul className={styles.list}>
      {items.map((item, index) => (
        <li key={`${item.event}-${item.date}`} className={styles.item} style={staggerStyle(index)}>
          <Head item={item} />
          <Disclosure summary={t("fsp.details")}>
            <Terms items={terms(item)} />
          </Disclosure>
        </li>
      ))}
    </ul>
  )
}

export function FspRecord({ card }: FspRecordProps) {
  const { t } = useTranslation("card")
  const details = card.fsp_details ?? []
  const brief = card.fsp_achievements
  return (
    <Card title={t("fsp.title")} description={t("fsp.lead")}>
      {details.length > 0 ? (
        <Detailed items={details} />
      ) : brief.length > 0 ? (
        <ul className={styles.list}>
          {brief.map((item, index) => (
            <li
              key={`${item.discipline.code}-${item.year}-${item.result}`}
              className={styles.item}
              style={staggerStyle(index)}
            >
              <Head item={item} />
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.empty}>
          <IconLabel icon="fsp" tone="secondary">
            {t("fsp.empty")}
          </IconLabel>
        </p>
      )}
    </Card>
  )
}
