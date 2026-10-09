import type { ReactNode } from "react"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { GradeRuler, SkillList, TrustBadge } from "@/entities/measure"
import type { CandidateCard as Card_ } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Banner, Card, Chip, IconLabel } from "@/shared/ui"
import { ContactsRecord } from "../contacts-record/contacts-record"
import { FspRecord } from "../fsp-record/fsp-record"
import { SelfRecord } from "../self-record/self-record"
import styles from "./candidate-card.module.css"

export interface CandidateCardViewProps {
  readonly card: Card_
  readonly invite: ReactNode
}

function Summary({ card }: { readonly card: Card_ }) {
  const { t } = useTranslation(["card", "measure"])
  const names = useCatalogNames()
  const status = card.grade_status
  const statusText =
    status === null
      ? null
      : status.kind === "confirmed"
        ? t("measure:gradeStatus.confirmed")
        : t(`measure:gradeStatus.${status.kind}` as never, {
            claimed: names.grade(status.claimed),
            confirmed: status.confirmed === null ? "" : names.grade(status.confirmed),
          })
  return (
    <Card level="inner" title={t("level")}>
      <div className={styles.summary}>
        {card.category === null ? (
          <IconLabel icon="alert" tone="secondary">
            {t("noCategory")}
          </IconLabel>
        ) : (
          <span className={styles.chips}>
            <Chip icon={specializationIcon(card.category.specialization.code)} tone="accent">
              {names.specialization(card.category.specialization)}
            </Chip>
            <Chip icon={gradeIcon(card.category.grade.code)} tone="accent">
              {names.grade(card.category.grade)}
            </Chip>
          </span>
        )}
        {statusText === null ? null : (
          <IconLabel
            icon={status?.kind === "confirmed" ? "test" : "alert"}
            tone={status?.kind === "confirmed" ? "secondary" : "danger"}
          >
            {statusText}
          </IconLabel>
        )}
        {card.category?.verified_at ? <TrustBadge source="verification" /> : null}
        {card.skill_profile === null ? null : (
          <GradeRuler level={card.skill_profile.overall} animate />
        )}
      </div>
    </Card>
  )
}

export function CandidateCardView({ card, invite }: CandidateCardViewProps) {
  const { t } = useTranslation("card")
  return (
    <div className={styles.layout}>
      <div className={styles.main}>
        {card.disclosed === null ? <Banner tone="info" icon="lock" title={t("anonymous")} /> : null}
        <Card title={t("skills.title")} description={t("skills.lead")}>
          {card.skill_profile === null ? (
            <p className={styles.empty}>{t("skills.empty")}</p>
          ) : (
            <SkillList topics={card.skill_profile.topics} label={t("skills.title")} animate />
          )}
        </Card>
        <FspRecord card={card} />
        <SelfRecord self={card.self_reported} />
      </div>
      <aside className={styles.aside}>
        {card.disclosed === null ? null : <ContactsRecord disclosed={card.disclosed} />}
        <Summary card={card} />
        <Card level="inner" title={t("invite.title")} description={t("invite.lead")}>
          <div className={styles.invite}>{invite}</div>
        </Card>
      </aside>
    </div>
  )
}
