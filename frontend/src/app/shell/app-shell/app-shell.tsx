import { useEffect, useRef } from "react"
import { Outlet, useLocation } from "react-router"
import { useUnreadMessages } from "@/entities/conversation"
import type { User } from "@/shared/api"
import { useMediaQuery, useStoredFlag } from "@/shared/hooks"
import { useTranslation } from "@/shared/i18n"
import { withViewTransition } from "@/shared/motion"
import { BottomNav } from "../bottom-nav/bottom-nav"
import { MobileBar } from "../mobile-bar/mobile-bar"
import { OfflineBanner } from "../offline-banner/offline-banner"
import { Sidebar } from "../sidebar/sidebar"
import styles from "./app-shell.module.css"

const MEDIUM = "(max-width: 63.99rem)"
const SIDEBAR_KEY = "calibr-sidebar"

function useRouteFocus(): void {
  const { pathname } = useLocation()
  const previous = useRef<string | null>(null)
  useEffect(() => {
    const changed = previous.current !== null && previous.current !== pathname
    previous.current = pathname
    if (!changed) return
    const frame = window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("#main h1")?.focus({ preventScroll: true })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [pathname])
}

export interface AppShellProps {
  readonly user: User
}

export function AppShell({ user }: AppShellProps) {
  const { t } = useTranslation()
  const medium = useMediaQuery(MEDIUM)
  const [stored, setStored] = useStoredFlag(SIDEBAR_KEY, false)
  const collapsed = stored || medium
  const unread = useUnreadMessages(user.role)
  useRouteFocus()

  const toggle = () => {
    void withViewTransition("layout", () => setStored(!collapsed))
  }

  return (
    <div className={styles.shell} data-collapsed={collapsed}>
      <a className={styles.skip} href="#main">
        {t("shell.skip")}
      </a>
      <div className={styles.side}>
        <Sidebar user={user} unread={unread} collapsed={collapsed} onToggle={toggle} />
      </div>
      <div className={styles.work}>
        <MobileBar user={user} />
        <OfflineBanner />
        <main id="main" tabIndex={-1} className={styles.main}>
          <Outlet />
        </main>
      </div>
      <BottomNav role={user.role} unread={unread} />
    </div>
  )
}
