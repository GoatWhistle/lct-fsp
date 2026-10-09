import { usePath } from "@/entities/candidate-path"
import { GradeRuler } from "@/entities/measure"
import type { FspAchievement, FspDivergence } from "@/shared/api"
import { BackendText, useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, Chip, IconLabel } from "@/shared/ui"
import styles from "./fsp-section.module.css"

export function Achievements({ items }: { readonly items: readonly FspAchievement[] }) {
  const { t } = useTranslation("profile")
  const catalog = useTranslation("catalog").t
  const names = useCatalogNames()
  const format = useFormatters()
  return (
    <ul className={styles.achievements} aria-label={t("fsp.achievements")}>
      {items.map((item, index) => (
        <li
          key={`${item.event}-${item.date}-${item.discipline.code}`}
          className={styles.achievement}
          style={staggerStyle(index)}
        >
          <div className={styles.achievementHead}>
            <BackendText className={styles.event}>{item.event}</BackendText>
            <Chip icon="fsp" tone={item.result === "participant" ? "neutral" : "accent"}>
              {catalog(`fspResult.${item.result}`)}
            </Chip>
          </div>
          <div className={styles.attributes}>
            <IconLabel icon="calendar" tone="secondary">
              {format.date(item.date)}
            </IconLabel>
            <IconLabel icon="topic" tone="secondary">
              {names.discipline(item.discipline)}
            </IconLabel>
            {item.place === null ? null : (
              <IconLabel icon="star" tone="secondary">
                {t("fsp.place", { place: item.place })}
              </IconLabel>
            )}
            {item.team_role === null ? null : (
              <IconLabel icon="candidates" tone="secondary">
                {names.specialization(item.team_role)}
              </IconLabel>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Divergences({ items }: { readonly items: readonly FspDivergence[] }) {
  const { t } = useTranslation("profile")
  const catalog = useTranslation("catalog").t
  const names = useCatalogNames()
  const path = usePath()
  const topics = path.data?.profile?.topics ?? []
  return (
    <Card level="inner" title={t("fsp.divergenceTitle")} description={t("fsp.divergenceText")}>
      <ul className={styles.divergences}>
        {items.map((item) => {
          const measured = topics.find((topic) => topic.topic.code === item.topic.code)
          const level = measured?.level ?? {
            theta: item.test_level,
            theta_sd: 0,
            band: { low: null, high: null, confident: false },
          }
          return (
            <li key={`${item.topic.code}-${item.event}`} className={styles.divergence}>
              <span className={styles.topic}>{names.topic(item.topic)}</span>
              <GradeRuler
                level={{ ...level, theta: item.test_level }}
                size="inline"
                caption
                secondary={{ theta: item.result_level, label: t("fsp.byFsp") }}
              />
              <IconLabel icon="fsp" tone="secondary">
                {t("fsp.divergenceEvent", {
                  event: item.event,
                  result: catalog(`fspResult.${item.result}`),
                })}
              </IconLabel>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
