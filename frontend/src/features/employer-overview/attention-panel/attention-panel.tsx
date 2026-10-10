import { Link } from "react-router"
import { useApplications } from "@/entities/application"
import { InvitationBudget, isOpenStatus, useSentInvitations } from "@/entities/invitation"
import { useNeeds } from "@/entities/need"
import { useAwaitingReview, useOwnTasks } from "@/entities/task"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, Icon, IconLabel, type IconName, Skeleton } from "@/shared/ui"
import { latestByNeed, useRecentSelections } from "../recent-selections"
import styles from "./attention-panel.module.css"

interface Alert {
  readonly key: string
  readonly icon: IconName
  readonly text: string
  readonly to: string
}

function useAlerts(): readonly Alert[] | undefined {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const sent = useSentInvitations()
  const applications = useApplications()
  const tasks = useOwnTasks()
  const waiting = useAwaitingReview(tasks.data)
  const needs = useNeeds()
  const selections = useRecentSelections()
  if (sent.data === undefined || applications.data === undefined) return undefined
  const latest = selections.data === undefined ? null : latestByNeed(selections.data)
  const unbuilt =
    needs.data === undefined || latest === null
      ? 0
      : needs.data.filter((need) => !latest.has(need.id)).length
  const unanswered = applications.data.filter(
    (item) => isOpenStatus(item.status) && item.revoked_at === null,
  ).length
  const unread = sent.data.invitations.filter((item) => item.unread_messages > 0).length
  const budget = sent.data.budget
  const alerts: (Alert | null)[] = [
    unbuilt === 0
      ? null
      : {
          key: "selections",
          icon: "match",
          text: t("overview.attention.selections", { count: unbuilt }),
          to: "/employer/needs",
        },
    unanswered === 0
      ? null
      : {
          key: "applications",
          icon: "application",
          text: t("overview.attention.applications", { count: unanswered }),
          to: "/employer/invitations?tab=applications",
        },
    unread === 0
      ? null
      : {
          key: "messages",
          icon: "message",
          text: t("overview.attention.messages", { count: unread }),
          to: "/employer/invitations",
        },
    waiting.size === 0
      ? null
      : {
          key: "tasks",
          icon: "task",
          text: t("overview.attention.tasks", { count: waiting.size }),
          to: "/employer/tasks?filter=review",
        },
    budget.remaining > 0
      ? null
      : {
          key: "budget",
          icon: "deadline",
          text: t("overview.attention.budget", { date: format.dateMoscow(budget.resets_at) }),
          to: "/employer/invitations",
        },
  ]
  return alerts.filter((alert): alert is Alert => alert !== null)
}

export interface AttentionPanelProps {
  readonly className?: string | undefined
}

export function AttentionPanel({ className }: AttentionPanelProps) {
  const { t } = useTranslation("employer")
  const alerts = useAlerts()
  const sent = useSentInvitations()
  return (
    <Card title={t("overview.attention.title")} className={className} motionIndex={2}>
      {alerts === undefined ? (
        <Skeleton lines={3} />
      ) : alerts.length === 0 ? (
        <IconLabel icon="accepted" tone="secondary" className={styles.calm}>
          {t("overview.attention.emptyTitle")}
        </IconLabel>
      ) : (
        <ul className={styles.list}>
          {alerts.map((alert, index) => (
            <li key={alert.key} className={styles.item} style={staggerStyle(index)}>
              <Link to={alert.to} className={styles.row} viewTransition>
                <Icon name={alert.icon} className={styles.icon} />
                <span>{alert.text}</span>
                <Icon name="chevron-right" size="sm" className={styles.chevron} />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {sent.data === undefined ? null : <InvitationBudget budget={sent.data.budget} />}
    </Card>
  )
}
