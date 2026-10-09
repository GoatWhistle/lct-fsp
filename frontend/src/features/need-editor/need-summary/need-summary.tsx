import { gradeIcon, specializationIcon, useTechnologies } from "@/entities/catalog"
import { useTopicImportance } from "@/entities/need"
import { useCatalogNames, useMoneyRange, useTranslation } from "@/shared/i18n"
import { Card, Chip, IconLabel } from "@/shared/ui"
import type { NeedForm } from "../need-form"
import styles from "./need-summary.module.css"

export interface NeedSummaryProps {
  readonly form: NeedForm
}

export function NeedSummary({ form }: NeedSummaryProps) {
  const { t } = useTranslation(["need", "common", "catalog"])
  const names = useCatalogNames()
  const money = useMoneyRange()
  const technologies = useTechnologies()
  const importance = useTopicImportance(
    form.specialization === null
      ? null
      : {
          specialization: form.specialization,
          stack: [...form.stack],
          topic_importance: { ...form.importance },
        },
  )
  const techName = new Map((technologies.data ?? []).map((tech) => [tech.code, tech.name]))
  const keyTopics = (importance.data ?? []).filter((row) => row.importance === "key")
  const salary = money(form.salaryFrom, form.salaryTo)

  return (
    <Card as="aside" level="inner" title={t("summary.title")} className={styles.summary}>
      <div className={styles.body}>
        <p className={styles.title} data-empty={form.title.trim() === ""}>
          {form.title.trim() === "" ? t("summary.untitled") : form.title}
        </p>
        <div className={styles.badges}>
          {form.specialization === null ? null : (
            <Chip icon={specializationIcon(form.specialization)} tone="accent">
              {names.specialization(form.specialization)}
            </Chip>
          )}
          {form.grade === null ? null : (
            <Chip icon={gradeIcon(form.grade)} tone="accent">
              {names.grade(form.grade)}
            </Chip>
          )}
        </div>
        {form.team.trim() === "" ? null : <p className={styles.team}>{form.team}</p>}
        <dl className={styles.facts}>
          <dt>{t("summary.key")}</dt>
          <dd className={styles.chips}>
            {keyTopics.length === 0
              ? t("summary.noValue")
              : keyTopics.map((row) => <Chip key={row.topic.code}>{names.topic(row.topic)}</Chip>)}
          </dd>
          <dt>{t("summary.stack")}</dt>
          <dd className={styles.chips}>
            {form.stack.length === 0
              ? t("summary.noValue")
              : form.stack.map((code) => <Chip key={code}>{techName.get(code) ?? code}</Chip>)}
          </dd>
          <dt>{t("conditions.format")}</dt>
          <dd>
            <IconLabel icon={form.format === "remote" ? "globe" : "city"}>
              {t(`catalog:workFormat.${form.format}` as never)}
              {form.format === "remote" || form.city.trim() === "" ? "" : `, ${form.city}`}
            </IconLabel>
          </dd>
          <dt>{t("conditions.salary")}</dt>
          <dd>
            {salary === null ? (
              t("summary.noValue")
            ) : (
              <span className={styles.money}>
                <IconLabel icon="money">{salary}</IconLabel>
                <span className={styles.basis}>{t("common:money.basis")}</span>
              </span>
            )}
          </dd>
        </dl>
      </div>
    </Card>
  )
}
