import type { ReactNode } from "react"
import { candidateTag, InvitationStatusBadge, isOpenStatus } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { BackendText, useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { Banner, ButtonLink, Card, type TermItem, Terms } from "@/shared/ui"
import { VacancyTestResult } from "../vacancy-test-result/vacancy-test-result"
import styles from "./invitation-detail.module.css"

export interface InvitationDetailProps {
  readonly invitation: Invitation
  readonly conversation?: ReactNode
}

function useTermItems(invitation: Invitation): readonly TermItem[] {
  const { t } = useTranslation(["employer", "common"])
  const format = useFormatters()
  const money = useMoneyRange()
  const when = (value: string | null) =>
    value === null ? (
      <span className={styles.notYet}>{t("invitations.terms.notYet")}</span>
    ) : (
      format.dateTimeMoscow(value)
    )
  return [
    {
      key: "salary",
      label: t("invitations.terms.salary"),
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
      prose: true,
      label: t("invitations.terms.contact"),
      icon: "mail",
      value: <BackendText>{invitation.contact}</BackendText>,
    },
    {
      key: "sent",
      label: t("invitations.terms.sent"),
      icon: "send",
      value: when(invitation.sent_at),
    },
    {
      key: "viewed",
      label: t("invitations.terms.viewed"),
      icon: "eye",
      value: when(invitation.viewed_at),
    },
    {
      key: "answered",
      label: t("invitations.terms.answered"),
      icon: "accepted",
      value: when(invitation.answered_at),
    },
    {
      key: "expires",
      label: t("invitations.terms.expires"),
      icon: "deadline",
      value: when(invitation.expires_at),
    },
  ]
}

export function InvitationDetail({ invitation, conversation }: InvitationDetailProps) {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const items = useTermItems(invitation)
  const open = isOpenStatus(invitation.status)
  return (
    <Card
      as="article"
      className={styles.detail}
      title={t("invitations.detail.title", { tag: candidateTag(invitation.candidate_id) })}
      description={t("invitations.detail.sentBy", { company: invitation.company_name })}
      actions={
        <ButtonLink
          to={`/employer/candidates/${invitation.candidate_id}`}
          variant="secondary"
          size="compact"
          icon="profile"
        >
          {t("invitations.detail.card")}
        </ButtonLink>
      }
    >
      <div className={styles.status}>
        <InvitationStatusBadge
          status={invitation.status}
          revoked={invitation.revoked_at !== null}
        />
      </div>
      {invitation.revoked_at === null ? null : (
        <Banner tone="attention" icon="revoked" title={t("invitations.detail.revokedTitle")}>
          {t("invitations.detail.revokedText", { date: format.dateMoscow(invitation.revoked_at) })}
        </Banner>
      )}
      {open ? (
        <Banner
          tone="info"
          icon="deadline"
          title={t("invitations.detail.waiting", {
            date: format.dateTimeMoscow(invitation.expires_at),
          })}
        >
          {t("invitations.detail.oneOpen")}
        </Banner>
      ) : null}
      <Terms items={items} />
      <section className={styles.section} aria-label={t("invitations.detail.description")}>
        <BackendText as="p" className={styles.description}>
          {invitation.description}
        </BackendText>
      </section>
      {invitation.vacancy_test === null ? null : (
        <VacancyTestResult test={invitation.vacancy_test} />
      )}
      {invitation.status === "accepted" ? conversation : null}
    </Card>
  )
}
