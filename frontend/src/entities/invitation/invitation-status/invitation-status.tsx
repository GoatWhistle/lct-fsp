import type { InvitationStatus } from "@/shared/api"
import { anonymousId } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { type IconName, StatusBadge, type StatusTone } from "@/shared/ui"

export type ResponseKind = "invitation" | "application"

export interface InvitationStatusBadgeProps {
  readonly status: InvitationStatus
  readonly kind?: ResponseKind
  readonly revoked?: boolean
  readonly className?: string | undefined
}

const TONE: Readonly<Record<InvitationStatus, StatusTone>> = {
  sent: "progress",
  viewed: "progress",
  accepted: "positive",
  declined: "neutral",
  expired: "neutral",
}

const ICON: Readonly<Record<InvitationStatus, IconName>> = {
  sent: "send",
  viewed: "eye",
  accepted: "accepted",
  declined: "declined",
  expired: "deadline",
}

export function isOpenStatus(status: InvitationStatus): boolean {
  return status === "sent" || status === "viewed"
}

export function candidateTag(candidateId: string): string {
  return anonymousId(candidateId)
}

export function InvitationStatusBadge({
  status,
  kind = "invitation",
  revoked = false,
  className,
}: InvitationStatusBadgeProps) {
  const { t } = useTranslation("employer")
  if (revoked)
    return (
      <StatusBadge tone="attention" icon="revoked" swapKey="revoked" className={className}>
        {t("status.revoked")}
      </StatusBadge>
    )
  return (
    <StatusBadge tone={TONE[status]} icon={ICON[status]} swapKey={status} className={className}>
      {t(`status.${kind}.${status}`)}
    </StatusBadge>
  )
}
