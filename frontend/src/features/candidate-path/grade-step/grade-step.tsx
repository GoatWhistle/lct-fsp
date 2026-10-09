import { useState } from "react"
import { useGradeHint, useStartAttempt } from "@/entities/candidate-path"
import { gradeIcon, useGrades } from "@/entities/catalog"
import type { Survey } from "@/shared/api"
import { useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Card, ChoiceTiles, Form, IconLabel, Skeleton } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

const TEST_MIN_ITEMS = 12
const TEST_MAX_ITEMS = 30

export interface GradeStepProps {
  readonly survey: Survey
  readonly onChangeDirection: () => void
  readonly onStarted: () => void
}

function HowPanel() {
  const { t } = useTranslation("path")
  return (
    <Card level="inner" title={t("how.title")}>
      <ul className={styles.points}>
        <li>
          <IconLabel icon="uncertainty">
            {t("how.length", { min: TEST_MIN_ITEMS, max: TEST_MAX_ITEMS })}
          </IconLabel>
        </li>
        <li>
          <IconLabel icon="clock">{t("how.leave")}</IconLabel>
        </li>
        <li>
          <IconLabel icon="verification">{t("how.server")}</IconLabel>
        </li>
        <li>
          <IconLabel icon="measure">{t("how.result")}</IconLabel>
        </li>
      </ul>
    </Card>
  )
}

export function GradeStep({ survey, onChangeDirection, onStarted }: GradeStepProps) {
  const { t } = useTranslation("path")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const grades = useGrades()
  const hint = useGradeHint()
  const start = useStartAttempt()
  const [chosen, setChosen] = useState<string | null>(null)
  const hinted = hint.data ?? null
  const value = chosen ?? hinted?.grade.code ?? null

  if (grades.data === undefined) return <Skeleton shape="block" />

  return (
    <Card
      title={t("grade.title")}
      description={names.specialization(survey.specialization)}
      className={styles.enter}
      actions={
        <Button variant="ghost" icon="edit" onClick={onChangeDirection}>
          {t("grade.change")}
        </Button>
      }
    >
      <Form onSubmit={() => value !== null && start.mutate(value, { onSuccess: onStarted })}>
        <div className={styles.split}>
          <div className={styles.stack}>
            {hinted === null ? null : (
              <Banner
                tone="info"
                icon="profile"
                title={t("grade.hint", { grade: names.grade(hinted.grade) })}
              />
            )}
            <ChoiceTiles
              legend={t("grade.title")}
              hideLegend
              columns="compact"
              value={value}
              onChange={setChosen}
              tiles={grades.data.map((grade) => ({
                value: grade.code,
                title: names.grade(grade),
                icon: gradeIcon(grade.code),
                description: t(`grade.${grade.code}` as never),
                badge: hinted?.grade.code === grade.code ? t("grade.byProfile") : undefined,
              }))}
            />
          </div>
          <HowPanel />
        </div>
        {start.isError && <Banner tone="critical" title={errorText(start.error)} />}
        <div className={styles.actions}>
          <Button
            type="submit"
            icon="test"
            disabled={value === null}
            pending={start.isPending}
            pendingLabel={t("grade.pending")}
          >
            {value === null
              ? t("grade.startEmpty")
              : t("grade.start", { grade: names.grade(value) })}
          </Button>
        </div>
      </Form>
    </Card>
  )
}
