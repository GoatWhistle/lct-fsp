import type { ReactNode } from "react"
import { GradeRuler, levelFrom, ProbabilityLabel, TrustBadge } from "@/entities/measure"
import { anonymousId, type SearchHit } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, IconLabel } from "@/shared/ui"
import styles from "./search-row.module.css"

export interface SearchRowProps {
  readonly hit: SearchHit
  readonly index: number
  readonly animate: boolean
  readonly invite: ReactNode
}

export function SearchRow({ hit, index, animate, invite }: SearchRowProps) {
  const { t } = useTranslation(["search", "measure"])
  const names = useCatalogNames()
  const status = hit.grade_status
  const confirmed = status.kind === "confirmed"
  const statusText = confirmed
    ? t("measure:gradeStatus.confirmed")
    : t(`measure:gradeStatus.${status.kind}` as never, {
        claimed: names.grade(status.claimed),
        confirmed: status.confirmed === null ? "" : names.grade(status.confirmed),
      })

  return (
    <li
      className={styles.row}
      data-animate={animate}
      data-confirmed={confirmed}
      style={staggerStyle(index)}
    >
      <span className={styles.position}>{hit.position}</span>
      <span className={styles.identity}>
        <span className={styles.id}>{anonymousId(hit.candidate_id)}</span>
        <IconLabel
          icon={confirmed ? "test" : "alert"}
          tone={confirmed ? "secondary" : "danger"}
          className={styles.status}
        >
          {statusText}
        </IconLabel>
      </span>
      <span className={styles.level}>
        {hit.theta === null || hit.theta_sd === null ? (
          <span className={styles.unmeasured}>{t("results.noLevel")}</span>
        ) : (
          <GradeRuler
            level={levelFrom(hit.theta, hit.theta_sd)}
            size="inline"
            caption={false}
            animate={animate}
          />
        )}
      </span>
      <span className={styles.facts} data-probability-surface>
        {hit.grade_probability === null ? null : (
          <span className={styles.probability}>
            {t("results.probability")}{" "}
            <ProbabilityLabel value={hit.grade_probability} label={t("results.probability")} />
          </span>
        )}
        {hit.fsp_confirmed ? <TrustBadge source="fsp" /> : null}
      </span>
      <span className={styles.actions}>
        {invite}
        <ButtonLink
          to={`/employer/candidates/${hit.candidate_id}`}
          variant="ghost"
          size="compact"
          icon="profile"
        >
          {t("results.card")}
        </ButtonLink>
      </span>
    </li>
  )
}
