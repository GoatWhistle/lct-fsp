import { useState } from "react"
import { useSaveNeed } from "@/entities/need"
import { useBuildSelection } from "@/entities/selection"
import type { Need, Selection } from "@/shared/api"
import { useMediaQuery } from "@/shared/hooks"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, Form, Trace } from "@/shared/ui"
import { ConditionsStep } from "../conditions-step/conditions-step"
import {
  inputOf,
  NEED_STEPS,
  type NeedErrors,
  type NeedForm,
  type NeedStep,
  stepErrors,
} from "../need-form"
import { NeedSummary } from "../need-summary/need-summary"
import { RequirementsStep } from "../requirements-step/requirements-step"
import { WhoStep } from "../who-step/who-step"
import styles from "./need-editor.module.css"

export interface NeedEditorProps {
  readonly needId: string | null
  readonly initial: NeedForm
  readonly uncertain?: ReadonlySet<string>
  readonly onSaved: (need: Need) => void
  readonly onBuilt: (selection: Selection) => void
}

const NONE: ReadonlySet<string> = new Set()

export function NeedEditor({
  needId,
  initial,
  uncertain = NONE,
  onSaved,
  onBuilt,
}: NeedEditorProps) {
  const { t } = useTranslation("need")
  const errorText = useErrorText()
  const [form, setForm] = useState(initial)
  const [step, setStep] = useState<NeedStep>("who")
  const [errors, setErrors] = useState<NeedErrors>({})
  const wide = useMediaQuery("(min-width: 120rem)")
  const save = useSaveNeed()
  const build = useBuildSelection()
  const index = NEED_STEPS.indexOf(step)
  const last = index === NEED_STEPS.length - 1
  const change = (patch: Partial<NeedForm>) => setForm((current) => ({ ...current, ...patch }))

  const firstInvalid = () =>
    NEED_STEPS.find((item) => Object.keys(stepErrors(form, item)).length > 0) ?? null

  const go = (target: NeedStep) => {
    setErrors({})
    setStep(target)
  }
  const next = () => {
    const found = stepErrors(form, step)
    if (Object.keys(found).length > 0) return setErrors(found)
    const following = NEED_STEPS[index + 1]
    if (following !== undefined) go(following)
  }
  const submit = (andBuild: boolean) => {
    const invalid = firstInvalid()
    if (invalid !== null) {
      setStep(invalid)
      setErrors(stepErrors(form, invalid))
      return
    }
    save.mutate(
      { id: needId, input: inputOf(form) },
      {
        onSuccess: (need) =>
          andBuild ? build.mutate(need.id, { onSuccess: onBuilt }) : onSaved(need),
      },
    )
  }
  const pending = save.isPending || build.isPending
  const failure = save.error ?? build.error

  return (
    <div className={styles.editor}>
      <Trace
        label={t("editor.steps")}
        orientation={wide ? "vertical" : "horizontal"}
        className={styles.trace}
        steps={NEED_STEPS.map((item, position) => ({
          key: item,
          title: (
            <Button
              variant="link"
              className={styles.stepLink}
              data-current={position === index}
              aria-current={position === index ? "step" : undefined}
              onClick={() => go(item)}
            >
              {t(`need:editor.${item}` as never)}
            </Button>
          ),
          status: position < index ? "done" : position === index ? "current" : "upcoming",
        }))}
      />
      <Form onSubmit={() => (last ? submit(true) : next())} className={styles.main}>
        <Swap swapKey={step} as="div">
          {step === "who" && (
            <WhoStep form={form} errors={errors} uncertain={uncertain} onChange={change} />
          )}
          {step === "requirements" && <RequirementsStep form={form} onChange={change} />}
          {step === "conditions" && (
            <ConditionsStep form={form} errors={errors} uncertain={uncertain} onChange={change} />
          )}
        </Swap>
        {failure === null ? null : <Banner tone="critical" title={errorText(failure)} />}
        <div className={styles.actions}>
          {index === 0 ? null : (
            <Button
              variant="ghost"
              icon="arrow-left"
              onClick={() => go(NEED_STEPS[index - 1] ?? step)}
            >
              {t("editor.back")}
            </Button>
          )}
          <Button
            type="submit"
            icon={last ? "match" : "arrow-right"}
            iconPosition={last ? "start" : "end"}
            pending={pending}
            pendingLabel={build.isPending ? t("editor.building") : t("editor.pending")}
          >
            {last ? (needId === null ? t("editor.create") : t("editor.update")) : t("editor.next")}
          </Button>
          <Button variant="secondary" disabled={pending} onClick={() => submit(false)}>
            {t("editor.save")}
          </Button>
        </div>
      </Form>
      <NeedSummary form={form} />
    </div>
  )
}
