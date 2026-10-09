import { useState } from "react"
import { useNavigate } from "react-router"
import { useStartAttempt } from "@/entities/candidate-path"
import { useGrades } from "@/entities/catalog"
import { useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Checkbox } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

export function LowerGrade({ pending }: { readonly pending: string }) {
  const { t } = useTranslation("test")
  const names = useCatalogNames()
  const errorText = useErrorText()
  const grades = useGrades()
  const navigate = useNavigate()
  const [consent, setConsent] = useState(false)
  const start = useStartAttempt(consent)
  const index = grades.data?.findIndex((grade) => grade.code === pending) ?? -1
  const lower = grades.data?.[index - 1]
  if (!lower) return null
  return (
    <div className={styles.stack}>
      <p>{t("protection.lowerText", { grade: names.grade(lower) })}</p>
      <Checkbox
        checked={consent}
        onChange={setConsent}
        label={t("protection.consent")}
        hint={t("protection.consentHint")}
      />
      {start.isError ? <Banner tone="critical" title={errorText(start.error)} /> : null}
      <div className={styles.actions}>
        <Button
          icon="test"
          variant="secondary"
          pending={start.isPending}
          onClick={() =>
            start.mutate(lower.code, {
              onSuccess: () => navigate("/candidate/test", { viewTransition: true }),
            })
          }
        >
          {t("protection.lowerAction", { grade: names.grade(lower) })}
        </Button>
      </div>
    </div>
  )
}
