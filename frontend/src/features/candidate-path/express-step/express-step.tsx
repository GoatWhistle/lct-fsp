import { useContinueExpress } from "@/entities/candidate-path"
import type { CandidatePath } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Card } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"
import { TestResult } from "../test-result/test-result"

export interface ExpressStepProps {
  readonly path: CandidatePath
  readonly onContinued: () => void
}

export function ExpressStep({ path, onContinued }: ExpressStepProps) {
  const { t } = useTranslation("path")
  const errorText = useErrorText()
  const proceed = useContinueExpress()
  return (
    <Card
      title={t("express.title")}
      description={t("express.text", { answered: path.express?.answered ?? 0 })}
      className={styles.enter}
    >
      <div className={styles.stack}>
        {path.result === null ? null : (
          <TestResult result={path.result} expressLimit={path.express?.limit} animate />
        )}
        {proceed.isError && <Banner tone="critical" title={errorText(proceed.error)} />}
        <div className={styles.actions}>
          <Button
            icon="test"
            pending={proceed.isPending}
            pendingLabel={t("express.pending")}
            onClick={() => proceed.mutate(undefined, { onSuccess: onContinued })}
          >
            {t("express.action")}
          </Button>
        </div>
      </div>
    </Card>
  )
}
