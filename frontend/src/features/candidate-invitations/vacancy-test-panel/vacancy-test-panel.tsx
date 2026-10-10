import { useNavigate } from "react-router"
import { PlanTopics } from "@/entities/vacancy-test"
import type { Invitation, VacancyTest } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, IconLabel } from "@/shared/ui"
import { useStartVacancyTest } from "./use-start-vacancy-test"
import styles from "./vacancy-test-panel.module.css"

export interface VacancyTestPanelProps {
  readonly invitation: Invitation
  readonly test: VacancyTest
}

function closed(invitation: Invitation): boolean {
  return invitation.status === "declined" || invitation.status === "expired"
}

export function VacancyTestPanel({ invitation, test }: VacancyTestPanelProps) {
  const { t } = useTranslation("vacancyTest")
  const errorText = useErrorText()
  const navigate = useNavigate()
  const start = useStartVacancyTest()
  const finished = test.status === "finished"
  const open = () => navigate("/candidate/test", { viewTransition: true })
  const action = () => {
    if (test.status === "in_progress") return open()
    start.mutate(invitation.id, { onSuccess: open })
  }
  return (
    <section className={styles.panel} aria-label={t("title")}>
      <IconLabel icon="test" className={styles.heading}>
        {t("title")}
      </IconLabel>
      <p className={styles.lead}>{t("candidate.lead")}</p>
      <PlanTopics plan={test.plan} />
      <Swap
        swapKey={finished ? "done" : closed(invitation) ? "closed" : test.status}
        className={styles.action}
      >
        {finished ? (
          <IconLabel icon="accepted" tone="accent">
            {t("candidate.done")}
          </IconLabel>
        ) : closed(invitation) ? (
          <IconLabel icon="lock" tone="secondary">
            {t("candidate.closed")}
          </IconLabel>
        ) : (
          <Button
            icon="test"
            pending={start.isPending}
            pendingLabel={t("loading")}
            onClick={action}
          >
            {test.status === "in_progress" ? t("candidate.continue") : t("candidate.start")}
          </Button>
        )}
      </Swap>
      {start.isError ? <Banner tone="critical" title={errorText(start.error)} /> : null}
    </section>
  )
}
