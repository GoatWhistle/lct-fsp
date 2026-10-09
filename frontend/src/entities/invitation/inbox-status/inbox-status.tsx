import type { InvitationStatus } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { type IconName, StatusBadge, type StatusTone } from "@/shared/ui"

export type InboxKind = "invitation" | "application"

export interface InboxStatusBadgeProps {
  readonly status: InvitationStatus
  readonly kind?: InboxKind
  readonly revoked?: boolean
  readonly className?: string | undefined
}

const TONE: Readonly<Record<InvitationStatus, StatusTone>> = {
  sent: "attention",
  viewed: "progress",
  accepted: "positive",
  declined: "neutral",
  expired: "neutral",
}

const ICON: Readonly<Record<InvitationStatus, IconName>> = {
  sent: "mail",
  viewed: "eye",
  accepted: "accepted",
  declined: "declined",
  expired: "deadline",
}

export function InboxStatusBadge({
  status,
  kind = "invitation",
  revoked = false,
  className,
}: InboxStatusBadgeProps) {
  const { t } = useTranslation("invitations")
  if (revoked)
    return (
      <StatusBadge tone="neutral" icon="revoked" swapKey="revoked" className={className}>
        {t("status.revoked")}
      </StatusBadge>
    )
  const tone = kind === "application" && status === "sent" ? "progress" : TONE[status]
  const icon = kind === "application" && status === "sent" ? "send" : ICON[status]
  return (
    <StatusBadge tone={tone} icon={icon} swapKey={status} className={className}>
      {t(`status.${kind}.${status}`)}
    </StatusBadge>
  )
}
