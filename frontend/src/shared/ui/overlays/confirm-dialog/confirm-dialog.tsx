import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "../../primitives/button/button"
import { Dialog } from "../dialog/dialog"

export type ConfirmTone = "default" | "danger"

export interface ConfirmDialogProps {
  readonly open: boolean
  readonly title: string
  readonly description?: string | undefined
  readonly confirmLabel: string
  readonly cancelLabel?: string | undefined
  readonly tone?: ConfirmTone
  readonly pending?: boolean
  readonly onConfirm: () => void
  readonly onClose: () => void
  readonly children?: ReactNode
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  tone = "default",
  pending = false,
  onConfirm,
  onClose,
  children,
}: ConfirmDialogProps) {
  const { t } = useTranslation()
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            {cancelLabel ?? t("action.cancel")}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            pending={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Dialog>
  )
}
