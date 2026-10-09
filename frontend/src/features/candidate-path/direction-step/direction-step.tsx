import { useState } from "react"
import { useSubmitSurvey } from "@/entities/candidate-path"
import { specializationIcon, useSpecializations } from "@/entities/catalog"
import { useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Card, ChoiceTiles, Form, Skeleton } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

export interface DirectionStepProps {
  readonly current: string | null
  readonly onCancel?: (() => void) | undefined
}

export function DirectionStep({ current, onCancel }: DirectionStepProps) {
  const { t } = useTranslation("path")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const specializations = useSpecializations()
  const submit = useSubmitSurvey()
  const firstWithTest = specializations.data?.find((item) => item.has_test)?.code ?? null
  const [chosen, setChosen] = useState<string | null>(current)
  const value = chosen ?? firstWithTest

  if (specializations.data === undefined) return <Skeleton shape="block" />

  return (
    <Card title={t("direction.title")} className={styles.enter}>
      <Form onSubmit={() => value !== null && submit.mutate(value)}>
        <ChoiceTiles
          legend={t("direction.title")}
          hideLegend
          value={value}
          onChange={setChosen}
          tiles={specializations.data.map((item) => ({
            value: item.code,
            title: names.specialization(item),
            icon: specializationIcon(item.code),
            description: t("direction.topics", { count: item.topics.length }),
            disabled: !item.has_test,
            disabledNote: t("direction.preparing"),
          }))}
        />
        <p className={styles.prose}>{t("direction.hint")}</p>
        {submit.isError && <Banner tone="critical" title={errorText(submit.error)} />}
        <div className={styles.actions}>
          <Button
            type="submit"
            icon="arrow-right"
            iconPosition="end"
            disabled={value === null}
            pending={submit.isPending}
            pendingLabel={t("direction.pending")}
          >
            {t("direction.next")}
          </Button>
          {onCancel === undefined ? null : (
            <Button variant="ghost" onClick={onCancel}>
              {t("direction.cancel")}
            </Button>
          )}
        </div>
      </Form>
    </Card>
  )
}
