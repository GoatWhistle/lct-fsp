import { useNavigate } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useBuildSelection } from "@/entities/selection"
import type { Need, SelectionSummary } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, ButtonLink, IconLabel, StatusBadge, Tooltip, toast } from "@/shared/ui"
import { candidateCount } from "../recent-selections"
import styles from "./need-row.module.css"

const STACK_SHOWN = 4

export interface NeedRowProps {
  readonly need: Need
  readonly latest: SelectionSummary | undefined
  readonly index: number
}

export function NeedRow({ need, latest, index }: NeedRowProps) {
  const { t } = useTranslation("employer")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const format = useFormatters()
  const navigate = useNavigate()
  const build = useBuildSelection()
  const rest = need.stack.length - STACK_SHOWN
  const count = latest === undefined ? null : candidateCount(latest)
  const rebuild = () =>
    build.mutate(need.id, {
      onSuccess: (selection) =>
        navigate(`/employer/selections/${selection.id}`, { viewTransition: true }),
      onError: (error) => toast.error(errorText(error)),
    })
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.main}>
        <ButtonLink to={`/employer/needs/${need.id}`} variant="link" className={styles.title}>
          {need.title}
        </ButtonLink>
        <div className={styles.meta}>
          <IconLabel icon={specializationIcon(need.specialization.code)} tone="secondary">
            {names.specialization(need.specialization)}
          </IconLabel>
          <IconLabel icon={gradeIcon(need.grade.code)} tone="secondary">
            {names.grade(need.grade)}
          </IconLabel>
        </div>
        {need.stack.length === 0 ? null : (
          <div className={styles.stack}>
            {need.stack.slice(0, STACK_SHOWN).map((tech) => (
              <span key={tech.code}>{tech.name}</span>
            ))}
            {rest > 0 ? <span>{t("overview.needs.more", { count: rest })}</span> : null}
          </div>
        )}
      </div>
      <div className={styles.status}>
        {latest === undefined ? (
          <StatusBadge tone="attention" swapKey="none">
            {t("overview.needs.noSelection")}
          </StatusBadge>
        ) : (
          <>
            <StatusBadge tone="progress" swapKey="built">
              {t("overview.needs.choosing")}
            </StatusBadge>
            <span className={styles.date}>
              {t("overview.needs.built", { date: format.dateTime(latest.created_at) })}
            </span>
          </>
        )}
      </div>
      <div className={styles.count}>
        {count === null ? null : (
          <>
            <span className={styles.value}>{format.integer(count)}</span>
            <span className={styles.unit}>{t("overview.needs.candidates", { count })}</span>
          </>
        )}
      </div>
      <div className={styles.actions}>
        {latest === undefined ? (
          <Button
            size="compact"
            icon="match"
            pending={build.isPending}
            pendingLabel={t("overview.needs.building")}
            onClick={rebuild}
          >
            {t("overview.needs.build")}
          </Button>
        ) : (
          <>
            <ButtonLink
              to={`/employer/selections/${latest.id}`}
              variant="secondary"
              size="compact"
              icon="match"
            >
              {t("overview.needs.open")}
            </ButtonLink>
            <Tooltip content={t("overview.needs.rebuild")}>
              <Button
                variant="ghost"
                size="icon"
                icon="refresh"
                pending={build.isPending}
                onClick={rebuild}
              >
                {t("overview.needs.rebuild")}
              </Button>
            </Tooltip>
          </>
        )}
      </div>
    </li>
  )
}
