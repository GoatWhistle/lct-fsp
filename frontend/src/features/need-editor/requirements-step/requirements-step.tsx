import { useMemo } from "react"
import { useTechnologies } from "@/entities/catalog"
import { useTopicImportance } from "@/entities/need"
import type { TopicImportance } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Banner, Card, Combobox, LoadError, Skeleton, Spinner } from "@/shared/ui"
import { ImportanceTable } from "../importance-table/importance-table"
import type { NeedForm } from "../need-form"
import styles from "./requirements-step.module.css"

export interface RequirementsStepProps {
  readonly form: NeedForm
  readonly onChange: (patch: Partial<NeedForm>) => void
}

export function RequirementsStep({ form, onChange }: RequirementsStepProps) {
  const { t } = useTranslation("need")
  const technologies = useTechnologies()
  const specialization = form.specialization
  const importance = useTopicImportance(
    specialization === null
      ? null
      : { specialization, stack: [...form.stack], topic_importance: { ...form.importance } },
  )
  const options = useMemo(
    () =>
      (technologies.data ?? [])
        .filter((tech) => tech.topics.some((topic) => topic.startsWith(`${specialization}.`)))
        .map((tech) => ({ value: tech.code, label: tech.name })),
    [technologies.data, specialization],
  )

  if (specialization === null)
    return <Banner tone="info" icon="info" title={t("requirements.noSpecialization")} />

  const setImportance = (topic: string, level: TopicImportance | null) => {
    const next = { ...form.importance }
    if (level === null) delete next[topic]
    else next[topic] = level
    onChange({ importance: next })
  }

  return (
    <div className={styles.step}>
      <Combobox
        label={t("requirements.stack")}
        hint={t("requirements.stackHint")}
        values={form.stack}
        options={options}
        onChange={(stack) => onChange({ stack })}
      />
      <Card
        level="inner"
        title={t("requirements.topics")}
        description={t("requirements.topicsLead")}
        actions={
          importance.isFetching ? (
            <Spinner size="sm" delayed label={t("requirements.recalculating")} />
          ) : null
        }
      >
        {importance.isError ? (
          <LoadError error={importance.error} onRetry={() => void importance.refetch()} />
        ) : importance.data === undefined ? (
          <Skeleton lines={6} />
        ) : (
          <ImportanceTable
            rows={importance.data}
            stale={importance.isPlaceholderData}
            onChange={setImportance}
          />
        )}
      </Card>
    </div>
  )
}
