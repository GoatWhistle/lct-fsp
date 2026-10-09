import { useState } from "react"
import { useNavigate } from "react-router"
import { useStartAttempt, useStepDown } from "@/entities/candidate-path"
import { gradeIcon } from "@/entities/catalog"
import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Banner, Button, ConfirmDialog, IconLabel, Menu, toast } from "@/shared/ui"
import { availableAt, TEST_ROUTE } from "../available-at"
import styles from "./grade-change.module.css"

export interface GradeChangeProps {
  readonly path: CandidatePath
}

export function GradeUp({ path }: GradeChangeProps) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const start = useStartAttempt()
  const up = path.grade_up
  if (up === null) return <p className={styles.note}>{t("gradeUp.top")}</p>
  const grade = names.grade(up.grade)
  const until = up.available_at ?? availableAt(start.error)
  const hinted = path.result?.grade_up_hint === up.grade && until === null

  const run = () =>
    start.mutate(up.grade, {
      onSuccess: () => navigate(TEST_ROUTE, { viewTransition: true }),
      onError: (error) => {
        if (availableAt(error) === null) toast.error(errorText(error))
      },
    })

  return (
    <div className={styles.up}>
      {hinted ? <Banner tone="info" icon="match" title={t("gradeUp.hint", { grade })} /> : null}
      <p className={styles.note}>{t("gradeUp.text", { grade })}</p>
      <div className={styles.actions}>
        <Button
          icon={gradeIcon(up.grade)}
          variant={hinted ? "primary" : "secondary"}
          disabled={until !== null}
          pending={start.isPending}
          pendingLabel={t("gradeUp.pending")}
          onClick={run}
        >
          {t("gradeUp.action", { grade })}
        </Button>
        {until === null ? null : (
          <IconLabel icon="calendar" tone="secondary" className={styles.date}>
            {t("gradeUp.from", { date: format.dateMoscow(until) })}
          </IconLabel>
        )}
      </div>
    </div>
  )
}

export function StepDownMenu({ path }: GradeChangeProps) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const stepDown = useStepDown()
  const [open, setOpen] = useState(false)
  if (path.grade_down === null) return null
  const grade = names.grade(path.grade_down)

  const confirm = () =>
    stepDown.mutate(undefined, {
      onSuccess: () => {
        setOpen(false)
        toast.success(t("stepDown.done", { grade }))
      },
      onError: (error) => toast.error(errorText(error)),
    })

  return (
    <>
      <Menu
        items={[
          {
            id: "step-down",
            label: t("stepDown.menu", { grade }),
            icon: gradeIcon(path.grade_down),
            onSelect: () => setOpen(true),
          },
        ]}
      />
      <ConfirmDialog
        open={open}
        tone="danger"
        title={t("stepDown.title", { grade })}
        description={t("stepDown.text")}
        confirmLabel={t("stepDown.confirm", { grade })}
        pending={stepDown.isPending}
        onConfirm={confirm}
        onClose={() => setOpen(false)}
      />
    </>
  )
}
