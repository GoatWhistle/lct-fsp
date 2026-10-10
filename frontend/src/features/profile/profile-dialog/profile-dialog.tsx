import { type ReactNode, useCallback, useRef, useState } from "react"
import { useSearchParams } from "react-router"
import { PROFILE_PARAM } from "@/entities/profile"
import { useTranslation } from "@/shared/i18n"
import { ConfirmDialog, Dialog, toast } from "@/shared/ui"
import { FspReturn } from "../fsp-return/fsp-return"
import { ProfileEditor } from "../profile-editor/profile-editor"
import styles from "./profile-dialog.module.css"

const FSP_PARAMS = ["fsp", "fsp_error"]

export interface ProfileDialogProps {
  readonly fspLinkAction: ReactNode
}

export function ProfileDialog({ fspLinkAction }: ProfileDialogProps) {
  const { t } = useTranslation(["profile", "common"])
  const [params, setParams] = useSearchParams()
  const open = params.has(PROFILE_PARAM)
  const focus = params.get(PROFILE_PARAM) === "fsp" ? "fsp" : null
  const dirty = useRef(false)
  const [confirming, setConfirming] = useState(false)

  const close = useCallback(() => {
    dirty.current = false
    setConfirming(false)
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete(PROFILE_PARAM)
        for (const key of FSP_PARAMS) next.delete(key)
        return next
      },
      { replace: true },
    )
  }, [setParams])

  const requestClose = () => (dirty.current ? setConfirming(true) : close())

  const onSaved = () => {
    close()
    toast.success(t("save.done"))
  }

  const onDirtyChange = useCallback((next: boolean) => {
    dirty.current = next
  }, [])

  return (
    <>
      <Dialog open={open} onClose={requestClose} title={t("title")} size="sheet">
        <div className={styles.body}>
          <FspReturn />
          <ProfileEditor
            fspLinkAction={fspLinkAction}
            focus={focus}
            onSaved={onSaved}
            onDirtyChange={onDirtyChange}
          />
        </div>
      </Dialog>
      <ConfirmDialog
        open={confirming}
        title={t("common:leave.title")}
        description={t("common:leave.text")}
        confirmLabel={t("common:leave.leave")}
        cancelLabel={t("common:leave.stay")}
        tone="danger"
        onConfirm={close}
        onClose={() => setConfirming(false)}
      />
    </>
  )
}
