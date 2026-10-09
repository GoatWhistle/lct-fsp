import { useState } from "react"
import { useNavigate } from "react-router"
import { type ApplicationAction, useApplicationAction } from "@/entities/application"
import { candidateTag, InvitationStatusBadge, isOpenStatus } from "@/entities/invitation"
import type { Application } from "@/shared/api"
import { useErrorText, useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { Banner, Button, Card, ConfirmDialog, type TermItem, Terms, toast } from "@/shared/ui"
import styles from "./application-detail.module.css"

export interface ApplicationDetailProps {
  readonly application: Application
}

type Decision = Exclude<ApplicationAction, "view">

const URGENT_MS = 2 * 24 * 60 * 60 * 1000

function useTermItems(application: Application): readonly TermItem[] {
  const { t } = useTranslation(["applications", "common"])
  const format = useFormatters()
  const money = useMoneyRange()
  const when = (value: string | null) =>
    value === null ? (
      <span className={styles.notYet}>{t("terms.notYet")}</span>
    ) : (
      format.dateTimeMoscow(value)
    )
  const soon = Date.parse(application.expires_at) - Date.now() < URGENT_MS
  return [
    {
      key: "salary",
      label: t("terms.salary"),
      icon: "money",
      value: (
        <>
          {money(application.salary_from, application.salary_to)}
          <span className={styles.basis}>{t("common:money.basis")}</span>
        </>
      ),
    },
    {
      key: "applied",
      label: t("terms.applied"),
      icon: "send",
      value: when(application.applied_at),
    },
    { key: "viewed", label: t("terms.viewed"), icon: "eye", value: when(application.viewed_at) },
    {
      key: "expires",
      label: t("terms.expires"),
      icon: "deadline",
      value: when(application.expires_at),
      tone: isOpenStatus(application.status) && soon ? "danger" : "default",
    },
  ]
}

export function ApplicationDetail({ application }: ApplicationDetailProps) {
  const { t } = useTranslation("applications")
  const errorText = useErrorText()
  const navigate = useNavigate()
  const view = useApplicationAction("view")
  const accept = useApplicationAction("accept")
  const decline = useApplicationAction("decline")
  const [asked, setAsked] = useState<Decision | null>(null)
  const items = useTermItems(application)
  const open = isOpenStatus(application.status)
  const revoked = application.revoked_at !== null
  const profile = `/employer/candidates/${application.candidate_id}`
  const openProfile = () =>
    view.mutate(application.id, {
      onSuccess: () => navigate(profile, { viewTransition: true }),
      onError: (error) => toast.error(errorText(error)),
    })
  const decide = (decision: Decision) => {
    const mutation = decision === "accept" ? accept : decline
    mutation.mutate(application.id, {
      onSuccess: () => {
        setAsked(null)
        toast.success(t(`done.${decision}`))
      },
      onError: (error) => {
        setAsked(null)
        toast.error(errorText(error))
      },
    })
  }
  return (
    <Card
      as="article"
      className={styles.detail}
      title={application.vacancy_title}
      description={t("detail.candidate", { tag: candidateTag(application.candidate_id) })}
    >
      <div className={styles.status}>
        <InvitationStatusBadge status={application.status} kind="application" revoked={revoked} />
      </div>
      {revoked ? (
        <Banner tone="attention" icon="revoked" title={t("detail.revokedTitle")}>
          {t("detail.revokedText")}
        </Banner>
      ) : null}
      <Terms items={items} />
      <div className={styles.actions}>
        <Button
          variant={open ? "secondary" : "primary"}
          icon="profile"
          pending={view.isPending}
          pendingLabel={t("detail.opening")}
          onClick={openProfile}
        >
          {revoked ? t("detail.openAnonymous") : t("detail.open")}
        </Button>
        {open ? (
          <>
            <Button icon="accepted" onClick={() => setAsked("accept")}>
              {t("detail.accept")}
            </Button>
            <Button variant="ghost" icon="declined" onClick={() => setAsked("decline")}>
              {t("detail.decline")}
            </Button>
          </>
        ) : null}
      </div>
      <ConfirmDialog
        open={asked !== null}
        title={t(`confirm.${asked ?? "accept"}.title`)}
        description={t(`confirm.${asked ?? "accept"}.text`)}
        confirmLabel={t(`confirm.${asked ?? "accept"}.action`)}
        tone={asked === "decline" ? "danger" : "default"}
        pending={accept.isPending || decline.isPending}
        onConfirm={() => asked !== null && decide(asked)}
        onClose={() => setAsked(null)}
      />
    </Card>
  )
}
