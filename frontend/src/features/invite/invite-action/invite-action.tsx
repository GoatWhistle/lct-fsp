import { useState } from "react"
import { InvitationStatusBadge, useSentInvitations } from "@/entities/invitation"
import type { InvitationStatus } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, type ButtonSize } from "@/shared/ui"
import { type InviteDefaults, InviteDialog } from "../invite-dialog/invite-dialog"

const OPEN: ReadonlySet<InvitationStatus> = new Set(["sent", "viewed", "accepted"])

export interface InviteActionProps {
  readonly candidateId: string
  readonly label: string
  readonly defaults: InviteDefaults
  readonly size?: ButtonSize
}

export function InviteAction({
  candidateId,
  label,
  defaults,
  size = "compact",
}: InviteActionProps) {
  const { t } = useTranslation("selection")
  const format = useFormatters()
  const sent = useSentInvitations()
  const [open, setOpen] = useState(false)
  const [opened, setOpened] = useState(false)
  const budget = sent.data?.budget ?? null
  const current = sent.data?.invitations.find(
    (item) => item.candidate_id === candidateId && item.revoked_at === null,
  )

  const status = current !== undefined && OPEN.has(current.status) ? current.status : null
  const exhausted = budget !== null && budget.remaining <= 0
  return (
    <>
      <Swap swapKey={status ?? "action"}>
        {status !== null ? (
          <InvitationStatusBadge status={status} />
        ) : (
          <Button
            size={size}
            variant="secondary"
            icon="invitation"
            disabled={exhausted || sent.data === undefined}
            disabledReason={
              budget === null
                ? undefined
                : t("invite.budgetEmpty", { date: format.date(budget.resets_at) })
            }
            onClick={() => {
              setOpened(true)
              setOpen(true)
            }}
          >
            {t("invite.action")}
          </Button>
        )}
      </Swap>
      {opened ? (
        <InviteDialog
          open={open}
          onClose={() => setOpen(false)}
          candidateId={candidateId}
          label={label}
          defaults={defaults}
          budget={budget}
        />
      ) : null}
    </>
  )
}
