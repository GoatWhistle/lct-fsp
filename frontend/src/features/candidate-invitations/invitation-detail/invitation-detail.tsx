import type { ReactNode } from "react"
import { InboxStatusBadge, isOpenStatus } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { BackendText, useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { Banner, Card, IconLabel, NoValue, type TermItem, Terms } from "@/shared/ui"
import { InvitationActions } from "../invitation-actions/invitation-actions"
import styles from "./invitation-detail.module.css"

const URGENT_MS = 48 * 60 * 60 * 1000

export interface InvitationDetailProps {
  readonly invitation: Invitation
  readonly conversation?: ReactNode
}

function isUrgent(invitation: Invitation): boolean {
  if (!isOpenStatus(invitation.status)) return false
  return new Date(invitation.expires_at).getTime() - Date.now() < URGENT_MS
}

function useTermItems(invitation: Invitation): readonly TermItem[] {
  const { t } = useTranslation(["invitations", "common"])
  const format = useFormatters()
  const money = useMoneyRange()
  const open = isOpenStatus(invitation.status)
  const answered =
    invitation.answered_at === null ? <NoValue /> : format.dateTimeMoscow(invitation.answered_at)
  return [
    {
      key: "salary",
      label: t("terms.salary"),
      icon: "money",
      value: (
        <>
          {money(invitation.salary_from, invitation.salary_to)}
          <span className={styles.basis}>{t("common:money.basis")}</span>
        </>
      ),
    },
    {
      key: "contact",
      label: t("terms.contact"),
      icon: "mail",
      value: <BackendText className={styles.text}>{invitation.contact}</BackendText>,
    },
    {
      key: "sent",
      label: t("terms.sent"),
      icon: "send",
      value: format.dateTimeMoscow(invitation.sent_at),
    },
    open
      ? {
          key: "expires",
          label: t("terms.expires"),
          icon: "deadline",
          value: format.dateTimeMoscow(invitation.expires_at),
          tone: isUrgent(invitation) ? "danger" : "default",
        }
      : { key: "answered", label: t("terms.answered"), icon: "accepted", value: answered },
  ]
}

function StateNote({ invitation }: { readonly invitation: Invitation }) {
  const { t } = useTranslation("invitations")
  const format = useFormatters()
  if (invitation.revoked_at !== null)
    return (
      <Banner tone="info" icon="revoked" title={t("detail.revokedTitle")}>
        {t("detail.revokedText", { date: format.dateMoscow(invitation.revoked_at) })}
      </Banner>
    )
  if (isUrgent(invitation))
    return (
      <Banner tone="attention" icon="deadline" title={t("detail.urgentTitle")}>
        {t("detail.urgentText", { date: format.dateTimeMoscow(invitation.expires_at) })}
      </Banner>
    )
  if (isOpenStatus(invitation.status))
    return (
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("detail.privacy")}
      </IconLabel>
    )
  return null
}

export function InvitationDetail({ invitation, conversation }: InvitationDetailProps) {
  const { t } = useTranslation("invitations")
  const format = useFormatters()
  const items = useTermItems(invitation)
  const talking = invitation.status === "accepted" && invitation.revoked_at === null
  return (
    <Card
      as="article"
      className={styles.detail}
      title={<BackendText>{invitation.company_name}</BackendText>}
      description={t("detail.received", { date: format.date(invitation.sent_at) })}
      actions={<InvitationActions invitation={invitation} part="menu" />}
    >
      <div className={styles.status}>
        <InboxStatusBadge status={invitation.status} revoked={invitation.revoked_at !== null} />
      </div>
      <StateNote invitation={invitation} />
      <Terms items={items} />
      <section className={styles.section} aria-label={t("detail.description")}>
        <BackendText as="p" className={styles.description}>
          {invitation.description}
        </BackendText>
      </section>
      <InvitationActions invitation={invitation} part="decision" />
      {talking ? (
        <section className={styles.section} aria-label={t("detail.conversation")}>
          <IconLabel icon="message" className={styles.heading}>
            {t("detail.conversation")}
          </IconLabel>
          {conversation}
        </section>
      ) : null}
    </Card>
  )
}
