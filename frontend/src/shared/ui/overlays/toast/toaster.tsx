import { useCallback, useEffect, useRef, useSyncExternalStore } from "react"
import { createPortal } from "react-dom"
import { type DurationToken, motionMs, usePresence } from "../../../motion"
import { Button } from "../../primitives/button/button"
import { CloseButton } from "../../primitives/close-button/close-button"
import { Icon, type IconName } from "../../primitives/icon/icon"
import { useLayerHost } from "../layer-host/layer-host"
import {
  dismissToast,
  readToasts,
  subscribeToasts,
  type ToastItem,
  type ToastTone,
} from "./toast-store"
import styles from "./toaster.module.css"

const TONE_ICON: Readonly<Record<ToastTone, IconName>> = {
  success: "accepted",
  error: "alert",
  info: "info",
}

const LIFETIME_TOKEN: Readonly<Record<ToastTone, DurationToken>> = {
  success: "--toast-lifetime",
  error: "--toast-lifetime-error",
  info: "--toast-lifetime",
}

function ToastCard({ item }: { readonly item: ToastItem }) {
  const timer = useRef<number | undefined>(undefined)
  const presence = usePresence(true)

  const start = useCallback(() => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(
      () => dismissToast(item.id),
      motionMs(LIFETIME_TOKEN[item.tone]),
    )
  }, [item.id, item.tone])
  const pause = useCallback(() => window.clearTimeout(timer.current), [])

  useEffect(() => {
    start()
    return pause
  }, [start, pause])

  return (
    <li
      className={styles.toast}
      data-tone={item.tone}
      data-state={presence.state}
      data-motion="fade"
      onPointerEnter={pause}
      onPointerLeave={start}
      onFocus={pause}
      onBlur={start}
    >
      <Icon name={TONE_ICON[item.tone]} size="md" className={styles.icon} />
      <p className={styles.message}>{item.message}</p>
      {item.action === undefined ? null : (
        <Button
          variant="ghost"
          size="compact"
          onClick={() => {
            item.action?.onAction()
            dismissToast(item.id)
          }}
        >
          {item.action.label}
        </Button>
      )}
      <CloseButton onClick={() => dismissToast(item.id)} />
    </li>
  )
}

export function Toaster() {
  const items = useSyncExternalStore(subscribeToasts, readToasts, readToasts)
  const host = useLayerHost()
  const latestPolite = items.filter((item) => item.tone !== "error").at(-1)
  const latestAlert = items.filter((item) => item.tone === "error").at(-1)
  return createPortal(
    <>
      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {latestPolite?.message}
      </div>
      <div className="visually-hidden" aria-live="assertive" aria-atomic="true">
        {latestAlert?.message}
      </div>
      <ol className={styles.viewport}>
        {items.map((item) => (
          <ToastCard key={item.id} item={item} />
        ))}
      </ol>
    </>,
    host,
  )
}
