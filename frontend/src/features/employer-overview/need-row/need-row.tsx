import { useNavigate } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useBuildSelection, useSelections } from "@/entities/selection"
import type { Need } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, ButtonLink, Chip, IconLabel, Trace, toast } from "@/shared/ui"
import styles from "./need-row.module.css"

const STACK_SHOWN = 5

export interface NeedRowProps {
  readonly need: Need
  readonly index: number
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
        {latest === undefined ? null : (
          <IconLabel icon="clock" tone="secondary" size="sm">
            {t("overview.needs.built", { date: format.dateTime(latest.created_at) })}
          </IconLabel>
        )}
      </div>
      <Trace
        label={t("overview.needs.trace.label")}
        orientation="horizontal"
        animate
        className={styles.trace}
        steps={[
          { key: "described", title: t("overview.needs.trace.described"), status: "done" },
          {
            key: "selection",
            title: t("overview.needs.trace.selection"),
            description:
              latest === undefined
                ? t("overview.needs.noSelection")
                : t("overview.needs.counts", {
                    exact: format.integer(latest.exact_total),
                    nearby: format.integer(latest.nearby_total),
                  }),
            status: latest === undefined ? "current" : "done",
          },
          {
            key: "invite",
            title: t("overview.needs.trace.invite"),
            description: t("overview.needs.trace.inviteHint"),
            status: latest === undefined ? "upcoming" : "current",
          },
        ]}
      />
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
