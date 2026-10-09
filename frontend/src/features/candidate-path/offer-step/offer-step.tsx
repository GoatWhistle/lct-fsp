import { useState } from "react"
import { useStartAttempt } from "@/entities/candidate-path"
import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Card, Checkbox } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"
import { TestResult } from "../test-result/test-result"

export interface OfferStepProps {
  readonly path: CandidatePath
  readonly onStarted: () => void
}

export function OfferStep({ path, onStarted }: OfferStepProps) {
  const { t } = useTranslation(["path", "test"])
  const names = useCatalogNames()
  const errorText = useErrorText()
  const [consent, setConsent] = useState(false)
  const start = useStartAttempt(consent)
  const offer = path.offer_grade ?? ""
  const tried = path.result?.grade ?? ""
  return (
    <Card
      title={t("offer.title", { grade: names.grade(tried) })}
      description={t("offer.text", { offer: names.grade(offer) })}
      className={styles.enter}
    >
      <div className={styles.stack}>
        {path.result === null ? null : <TestResult result={path.result} animate />}
        <Checkbox
          checked={consent}
          onChange={setConsent}
          label={t("test:protection.consent")}
          hint={t("test:protection.consentHint")}
        />
        {start.isError && <Banner tone="critical" title={errorText(start.error)} />}
        <div className={styles.actions}>
          <Button
            icon="test"
            pending={start.isPending}
            pendingLabel={t("offer.pending")}
            onClick={() => start.mutate(offer, { onSuccess: onStarted })}
          >
            {t("offer.action", { offer: names.grade(offer) })}
          </Button>
        </div>
      </div>
    </Card>
  )
}
