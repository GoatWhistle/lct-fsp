import { clsx } from "clsx"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button } from "@/shared/ui"
import { useJuryCandidate, useJuryEmployer, useJuryEnabled } from "../jury.queries"
import styles from "./jury-actions.module.css"

export interface JuryActionsProps {
  readonly className?: string | undefined
}

export function JuryActions({ className }: JuryActionsProps) {
  const { t } = useTranslation("auth")
  const errorText = useErrorText()
  const enabled = useJuryEnabled()
  const employer = useJuryEmployer()
  const candidate = useJuryCandidate()
  if (!enabled) return null
  const busy = employer.isPending || candidate.isPending
  const failed = employer.error ?? candidate.error
  return (
    <section className={clsx(styles.box, className)} aria-label={t("jury.label")}>
      <p className={styles.label}>{t("jury.label")}</p>
      <p className={styles.hint}>{t("jury.hint")}</p>
      <div className={styles.actions}>
        <Button
          variant="secondary"
          icon="company"
          fullWidth
          disabled={busy && !employer.isPending}
          pending={employer.isPending}
          onClick={() => {
            candidate.reset()
            employer.mutate()
          }}
        >
          {t("jury.employer")}
        </Button>
        <Button
          variant="secondary"
          icon="test"
          fullWidth
          disabled={busy && !candidate.isPending}
          pending={candidate.isPending}
          onClick={() => {
            employer.reset()
            candidate.mutate()
          }}
        >
          {t("jury.candidate")}
        </Button>
      </div>
      {failed !== null && <Banner tone="critical" title={errorText(failed)} />}
    </section>
  )
}
