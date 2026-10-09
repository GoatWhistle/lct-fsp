import type { ReactNode } from "react"
import { useNavigate } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useBuildDraftSelection } from "@/entities/selection"
import type { DraftField, NeedDraft } from "@/shared/api"
import { useCatalogNames, useErrorText, useMoneyRange, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Banner, Button, Card, Chip, IconLabel, type IconName, NoValue } from "@/shared/ui"
import { inputOfDraft } from "../draft-input"
import styles from "./draft-result.module.css"

export interface DraftResultProps {
  readonly draft: NeedDraft
}

interface Row {
  readonly field: DraftField | "title"
  readonly icon: IconName
  readonly value: ReactNode
}

export function DraftResult({ draft }: DraftResultProps) {
  const { t } = useTranslation(["need", "catalog"])
  const names = useCatalogNames()
  const money = useMoneyRange()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const build = useBuildDraftSelection()
  const input = inputOfDraft(draft)
  const uncertain = new Set<string>(draft.uncertain)

  const rows: readonly Row[] = [
    { field: "title", icon: "need", value: draft.title },
    {
      field: "specialization",
      icon: specializationIcon(draft.specialization?.code ?? ""),
      value: draft.specialization === null ? null : names.specialization(draft.specialization),
    },
    {
      field: "grade",
      icon: gradeIcon(draft.grade?.code ?? ""),
      value: draft.grade === null ? null : names.grade(draft.grade),
    },
    {
      field: "stack",
      icon: "test",
      value:
        draft.stack.length === 0 ? null : (
          <span className={styles.chips}>
            {draft.stack.map((tech) => (
              <Chip key={tech.code}>{tech.name}</Chip>
            ))}
          </span>
        ),
    },
    {
      field: "work_format",
      icon: "company",
      value:
        draft.work_format === null ? null : t(`catalog:workFormat.${draft.work_format}` as never),
    },
    { field: "city", icon: "city", value: draft.city },
    { field: "salary", icon: "money", value: money(draft.salary_from, draft.salary_to) },
  ]

  return (
    <Card title={t("text.draft")} description={t("text.draftLead")} className={styles.result}>
      <dl className={styles.fields}>
        {rows.map((row, index) => (
          <div key={row.field} className={styles.field} style={staggerStyle(index)}>
            <dt>
              <IconLabel icon={row.icon} tone="secondary" className={styles.label}>
                {t(`need:text.fields.${row.field}` as never)}
              </IconLabel>
            </dt>
            <dd className={styles.value}>
              {row.value === null ? <NoValue /> : row.value}
              {uncertain.has(row.field) ? (
                <IconLabel icon="alert" tone="danger" className={styles.flag}>
                  {t("text.uncertain")}
                </IconLabel>
              ) : null}
            </dd>
          </div>
        ))}
      </dl>
      {build.isError ? <Banner tone="critical" title={errorText(build.error)} /> : null}
      <div className={styles.actions}>
        <Button
          icon="edit"
          onClick={() =>
            navigate("/employer/needs/new", { state: { draft }, viewTransition: true })
          }
        >
          {t("text.toEditor")}
        </Button>
        <Button
          variant="secondary"
          icon="match"
          disabled={input === null}
          disabledReason={t("text.needsFields")}
          pending={build.isPending}
          onClick={() =>
            input !== null &&
            build.mutate(input, {
              onSuccess: (selection) =>
                navigate(`/employer/selections/${selection.id}`, { viewTransition: true }),
            })
          }
        >
          {t("text.buildDraft")}
        </Button>
      </div>
      {input === null ? <p className={styles.hint}>{t("text.needsFields")}</p> : null}
    </Card>
  )
}
