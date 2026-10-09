import { useState } from "react"
import { type InboxAction, isOpenStatus, useInboxAction } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { useLatched } from "@/shared/motion"
import { Button, ConfirmDialog, Menu, toast } from "@/shared/ui"
import styles from "./invitation-actions.module.css"

type Asked = Exclude<InboxAction, "view">

export interface InvitationActionsProps {
  readonly invitation: Invitation
  readonly part: "decision" | "menu"
}

function useAct(invitation: Invitation, close: () => void) {
  const { t } = useTranslation("invitations")
  const errorText = useErrorText()
  const accept = useInboxAction("accept")
  const decline = useInboxAction("decline")
  const revoke = useInboxAction("revoke")
  const mutations = { accept, decline, revoke }
  return {
    pending: accept.isPending || decline.isPending || revoke.isPending,
    run: (action: Asked) =>
      mutations[action].mutate(invitation.id, {
        onSuccess: () => {
          close()
          toast.success(t(`invitations:toast.${action}` as never))
        },
        onError: (error) => {
          close()
          toast.error(errorText(error))
        },
      }),
  }
}

export function InvitationActions({ invitation, part }: InvitationActionsProps) {
  const { t } = useTranslation(["invitations", "common"])
  const [asked, setAsked] = useState<Asked | null>(null)
  const act = useAct(invitation, () => setAsked(null))
  const shown = useLatched<Asked>(asked ?? "accept", asked !== null)
  const company = invitation.company_name
  const open = part === "decision" && isOpenStatus(invitation.status)
  const revocable =
    part === "menu" && invitation.status === "accepted" && invitation.revoked_at === null
  return (
    <>
      {open ? (
        <div className={styles.actions}>
          <Button icon="accepted" onClick={() => setAsked("accept")}>
            {t("action.accept")}
          </Button>
          <Button variant="secondary" icon="declined" onClick={() => setAsked("decline")}>
            {t("action.decline")}
          </Button>
        </div>
      ) : null}
      {revocable ? (
        <Menu
          label={t("common:action.more")}
          icon="more"
          iconOnly
          placement="bottom-end"
          items={[
            {
              id: "revoke",
              label: t("action.revoke"),
              icon: "revoked",
              onSelect: () => setAsked("revoke"),
            },
          ]}
        />
      ) : null}
      <ConfirmDialog
        open={asked !== null}
        tone={shown === "accept" ? "default" : "danger"}
        title={t(`invitations:confirm.${shown}.title` as never, { company })}
        description={t(`invitations:confirm.${shown}.text` as never, { company })}
        confirmLabel={t(`invitations:action.${shown}` as never)}
        pending={act.pending}
        onConfirm={() => act.run(shown)}
        onClose={() => setAsked(null)}
      />
    </>
  )
}
