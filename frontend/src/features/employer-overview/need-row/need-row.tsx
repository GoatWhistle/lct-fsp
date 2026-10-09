import { useNavigate } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useBuildSelection, useSelections } from "@/entities/selection"
import type { Need, SelectionSummary } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, ButtonLink, Chip, IconLabel, Skeleton, toast } from "@/shared/ui"
import styles from "./need-row.module.css"

const STACK_SHOWN = 5

export interface NeedRowProps {
  readonly need: Need
  readonly index: number
}

interface LatestSelectionProps {
  readonly latest: SelectionSummary | undefined
  readonly pending: boolean
}

function LatestSelection({ latest, pending }: LatestSelectionProps) {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  if (pending) return <Skeleton lines={2} className={styles.figures} />
  if (latest === undefined) return <p className={styles.none}>{t("overview.needs.noSelection")}</p>
  return (
    <dl className={styles.figures}>
      <div className={styles.figure}>
        <dt className={styles.figureLabel}>{t("overview.needs.exact")}</dt>
        <dd className={styles.figureValue}>{format.integer(latest.exact_total)}</dd>
      </div>
      <div className={styles.figure}>
        <dt className={styles.figureLabel}>{t("overview.needs.nearby")}</dt>
        <dd className={styles.figureValue}>{format.integer(latest.nearby_total)}</dd>
      </div>
    </dl>
  )
}

export function NeedRow({ need, index }: NeedRowProps) {
  const { t } = useTranslation("employer")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const format = useFormatters()
  const navigate = useNavigate()
  const selections = useSelections(need.id)
  const build = useBuildSelection()
  const latest = selections.data?.[0]
  const rest = need.stack.length - STACK_SHOWN
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
        <div className={styles.tags}>
          <Chip icon={specializationIcon(need.specialization.code)} tone="accent">
            {names.specialization(need.specialization)}
          </Chip>
          <Chip icon={gradeIcon(need.grade.code)} tone="accent">
            {names.grade(need.grade)}
          </Chip>
          {need.stack.slice(0, STACK_SHOWN).map((tech) => (
            <Chip key={tech.code}>{tech.name}</Chip>
          ))}
          {rest > 0 ? <Chip>{t("overview.needs.more", { count: rest })}</Chip> : null}
        </div>
      </div>
      <div className={styles.side}>
        <LatestSelection latest={latest} pending={selections.isPending} />
        {latest === undefined ? null : (
          <IconLabel icon="clock" tone="secondary" size="sm">
            {t("overview.needs.built", { date: format.dateTime(latest.created_at) })}
          </IconLabel>
        )}
      </div>
      <div className={styles.actions}>
        {latest === undefined ? null : (
          <ButtonLink to={`/employer/selections/${latest.id}`} size="compact" icon="match">
            {t("overview.needs.open")}
          </ButtonLink>
        )}
        <Button
          variant="secondary"
          size="compact"
          icon="refresh"
          pending={build.isPending}
          pendingLabel={t("overview.needs.building")}
          onClick={rebuild}
        >
          {latest === undefined ? t("overview.needs.build") : t("overview.needs.rebuild")}
        </Button>
      </div>
    </li>
  )
}
