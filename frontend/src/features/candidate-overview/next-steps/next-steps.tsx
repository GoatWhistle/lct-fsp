import { Link } from "react-router"
import { isOpenStatus, useInbox } from "@/entities/invitation"
import { PROFILE_DIALOG_LINK, PROFILE_FSP_LINK, useFspStatus, useProfile } from "@/entities/profile"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, Icon, IconLabel, type IconName, Skeleton } from "@/shared/ui"
import { completeness } from "../profile-completeness"
import styles from "./next-steps.module.css"

interface Step {
  readonly key: string
  readonly icon: IconName
  readonly text: string
  readonly to: string
}

function useSteps(): readonly Step[] | undefined {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const inbox = useInbox()
  const fsp = useFspStatus()
  const profile = useProfile()
  if (inbox.data === undefined && !inbox.isError) return undefined
  const invitations = inbox.data ?? []
  const open = invitations.filter(
    (item) => isOpenStatus(item.status) && item.revoked_at === null,
  ).length
  const unread = invitations.filter((item) => item.unread_messages > 0).length
  const ratio = profile.data === undefined ? 1 : completeness(profile.data)
  const steps: (Step | null)[] = [
    open === 0
      ? null
      : {
          key: "invitations",
          icon: "invitation",
          text: t("next.invitations", { count: open }),
          to: "/candidate/invitations",
        },
    unread === 0
      ? null
      : {
          key: "messages",
          icon: "message",
          text: t("next.messages", { count: unread }),
          to: "/candidate/invitations",
        },
    fsp.data?.linked === false
      ? { key: "fsp", icon: "fsp", text: t("next.fsp"), to: PROFILE_FSP_LINK }
      : null,
    ratio < 1
      ? {
          key: "profile",
          icon: "profile",
          text: t("next.profile", { value: format.percent(ratio) }),
          to: PROFILE_DIALOG_LINK,
        }
      : null,
  ]
  return steps.filter((step): step is Step => step !== null)
}

export interface NextStepsProps {
  readonly motionIndex?: number
  readonly className?: string | undefined
}

export function NextSteps({ motionIndex, className }: NextStepsProps) {
  const { t } = useTranslation("overview")
  const steps = useSteps()
  return (
    <Card title={t("next.title")} motionIndex={motionIndex} className={className}>
      {steps === undefined ? (
        <Skeleton lines={2} />
      ) : steps.length === 0 ? (
        <IconLabel icon="accepted" tone="secondary" className={styles.calm}>
          {t("next.empty")}
        </IconLabel>
      ) : (
        <ul className={styles.list}>
          {steps.map((step, index) => (
            <li key={step.key} className={styles.item} style={staggerStyle(index)}>
              <Link to={step.to} className={styles.row} viewTransition>
                <Icon name={step.icon} className={styles.icon} />
                <span>{step.text}</span>
                <Icon name="chevron-right" size="sm" className={styles.chevron} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
