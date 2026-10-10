import { clsx } from "clsx"
import { type ReactNode, type SyntheticEvent, useEffect, useId, useRef } from "react"
import { createPortal } from "react-dom"
import { usePresence } from "../../../motion"
import { CloseButton } from "../../primitives/close-button/close-button"
import { LayerHost, matchZoom, useLayerHost } from "../layer-host/layer-host"
import styles from "./dialog.module.css"

export interface DialogProps {
  readonly open: boolean
  readonly onClose: () => void
  readonly title: string
  readonly description?: string | undefined
  readonly actions?: ReactNode
  readonly size?: "regular" | "wide" | "sheet" | "drawer" | undefined
  readonly children?: ReactNode
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  actions,
  size = "regular",
  children,
}: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement | null>(null)
  const panelRef = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const descriptionId = useId()
  const presence = usePresence(open)
  const host = useLayerHost()

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null || !presence.mounted || dialog.open) return
    matchZoom(dialog, document.activeElement)
    if (typeof dialog.showModal === "function") dialog.showModal()
    else dialog.setAttribute("open", "")
    panelRef.current?.focus()
  }, [presence.mounted])

  if (!presence.mounted) return null

  const onCancel = (event: SyntheticEvent<HTMLDialogElement>) => {
    event.preventDefault()
    onClose()
  }

  return createPortal(
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      data-size={size}
      aria-labelledby={titleId}
      aria-describedby={description === undefined ? undefined : descriptionId}
      data-state={presence.state}
      onCancel={onCancel}
    >
      <div className={styles.scrim} data-motion="fade" aria-hidden="true" onClick={onClose} />
      <LayerHost>
        <section
          className={clsx(
            styles.panel,
            size === "wide" && styles.wide,
            size === "sheet" && styles.sheet,
            size === "drawer" && styles.drawer,
          )}
          tabIndex={-1}
          ref={panelRef}
          data-motion="fade"
          onAnimationEnd={presence.onAnimationEnd}
        >
          <header className={styles.header}>
            <hgroup className={styles.heading}>
              <h2 id={titleId} className={styles.title}>
                {title}
              </h2>
              {description === undefined ? null : (
                <p id={descriptionId} className={styles.description}>
                  {description}
                </p>
              )}
            </hgroup>
            <CloseButton onClick={onClose} />
          </header>
          {children === undefined ? null : <div className={styles.body}>{children}</div>}
          {actions === undefined ? null : <footer className={styles.actions}>{actions}</footer>}
        </section>
      </LayerHost>
    </dialog>,
    host,
  )
}
