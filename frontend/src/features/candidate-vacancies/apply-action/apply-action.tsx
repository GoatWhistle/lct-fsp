import { useState } from "react"
import { InboxStatusBadge } from "@/entities/invitation"
import { useApply } from "@/entities/vacancy"
import type { Application, Vacancy } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, ButtonLink, ConfirmDialog, toast } from "@/shared/ui"
import styles from "./apply-action.module.css"

export interface ApplyActionProps {
  readonly vacancy: Vacancy
  readonly application: Application | undefined
}

export function ApplyAction({ vacancy, application }: ApplyActionProps) {
  const { t } = useTranslation("vacancies")
  const errorText = useErrorText()
  const apply = useApply()
  const [asking, setAsking] = useState(false)
  const confirm = () =>
    apply.mutate(vacancy.id, {
      onSuccess: () => {
        setAsking(false)
        toast.success(t("toast.applied", { company: vacancy.company_name }))
      },
      onError: (error) => {
        setAsking(false)
        toast.error(errorText(error))
      },
    })
  return (
    <>
      <Swap
        swapKey={application === undefined ? "apply" : "applied"}
        as="div"
        className={styles.action}
      >
        {application === undefined ? (
          <Button icon="application" onClick={() => setAsking(true)}>
            {t("apply.action")}
          </Button>
        ) : (
          <>
            <InboxStatusBadge
              kind="application"
              status={application.status}
              revoked={application.revoked_at !== null}
            />
            <ButtonLink
              to="/candidate/vacancies?tab=applications"
              variant="secondary"
              icon="arrow-right"
              iconPosition="end"
            >
              {t("apply.toApplications")}
            </ButtonLink>
          </>
        )}
      </Swap>
      <ConfirmDialog
        open={asking}
        title={t("apply.title", { title: vacancy.title })}
        description={t("apply.text", { company: vacancy.company_name })}
        confirmLabel={t("apply.action")}
        pending={apply.isPending}
        onConfirm={confirm}
        onClose={() => setAsking(false)}
      />
    </>
  )
}
