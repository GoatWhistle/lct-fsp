import { useState } from "react"
import { useNavigate } from "react-router"
import { useStartAttempt, useStepDown } from "@/entities/candidate-path"
import { gradeIcon } from "@/entities/catalog"
import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import {
  Banner,
  Button,
  Checkbox,
  ConfirmDialog,
  Dialog,
  Disclosure,
  IconLabel,
  Menu,
  toast,
} from "@/shared/ui"
import { availableAt, TEST_ROUTE } from "../available-at"
import styles from "./grade-change.module.css"

export interface GradeChangeProps {
  readonly path: CandidatePath
}

export function GradeUp({ path }: GradeChangeProps) {
  const { t } = useTranslation(["overview", "test"])
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [consent, setConsent] = useState(false)
  const start = useStartAttempt(consent)
  const up = path.grade_up
  if (up === null) return <p className={styles.top}>{t("gradeUp.topShort")}</p>
  const grade = names.grade(up.grade)
  const until = up.available_at ?? availableAt(start.error)
  const hinted = path.result?.grade_up_hint === up.grade && until === null
  const from =
    until === null ? null : (
      <IconLabel icon="calendar" tone="secondary" className={styles.date}>
        {t("gradeUp.from", { date: format.dateMoscow(until) })}
      </IconLabel>
    )

  const run = () =>
    start.mutate(up.grade, {
      onSuccess: () => navigate(TEST_ROUTE, { viewTransition: true }),
      onError: (error) => {
        if (availableAt(error) === null) toast.error(errorText(error))
      },
    })

  return (
    <div className={styles.up}>
      {hinted ? (
        <IconLabel icon="match" tone="accent" className={styles.hint}>
          {t("gradeUp.hintShort")}
        </IconLabel>
      ) : null}
      <Button
        icon={gradeIcon(up.grade)}
        variant={hinted ? "primary" : "secondary"}
        size="compact"
        disabled={until !== null}
        onClick={() => setOpen(true)}
      >
        {t("gradeUp.action", { grade })}
      </Button>
      {from}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t("gradeUp.action", { grade })}
        description={t("gradeUp.text", { grade })}
        actions={
          <Button
            icon={gradeIcon(up.grade)}
            disabled={until !== null}
            pending={start.isPending}
            pendingLabel={t("gradeUp.pending")}
            onClick={run}
          >
            {t("gradeUp.start")}
          </Button>
        }
      >
        <div className={styles.dialog}>
          {hinted ? <Banner tone="info" icon="match" title={t("gradeUp.hint", { grade })} /> : null}
          <Checkbox checked={consent} onChange={setConsent} label={t("test:protection.consent")} />
          <Disclosure summary={<span className={styles.more}>{t("gradeUp.consentMore")}</span>}>
            <p className={styles.note}>{t("test:protection.consentHint")}</p>
          </Disclosure>
          {from}
        </div>
      </Dialog>
    </div>
  )
}

export function StepDownMenu({ path }: GradeChangeProps) {
  const { t } = useTranslation(["overview", "test"])
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
