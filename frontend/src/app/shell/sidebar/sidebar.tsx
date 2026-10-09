import { CABINET_PATH } from "@/entities/session"
import { AccountMenu } from "@/features/auth"
import { LocaleSwitch, ThemeSwitch } from "@/features/preferences"
import type { User } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, LockupLink, ScrollArea } from "@/shared/ui"
import styles from "./sidebar.module.css"
import { SidebarNav } from "./sidebar-nav"

export interface SidebarProps {
  readonly user: User
  readonly unread: number
  readonly collapsed: boolean
  readonly onToggle: () => void
}

export function Sidebar({ user, unread, collapsed, onToggle }: SidebarProps) {
  const { t } = useTranslation()
  const role = user.role === "candidate" ? t("shell.roleCandidate") : t("shell.roleEmployer")
  return (
    <aside className={styles.sidebar} data-surface="inverse" data-collapsed={collapsed}>
      <div className={styles.brand}>
        <LockupLink to={CABINET_PATH[user.role]} compact={collapsed} />
        {!collapsed && <span className={styles.role}>{role}</span>}
      </div>
      <ScrollArea label={t("shell.navigation")} className={styles.scroll}>
        <SidebarNav role={user.role} unread={unread} collapsed={collapsed} />
      </ScrollArea>
      <div className={styles.footer}>
        {!collapsed && (
          <span className={styles.email} title={user.email}>
            {user.email}
          </span>
        )}
        <div className={styles.account}>
          <AccountMenu user={user} iconOnly={collapsed} />
        </div>
        <div className={styles.tools}>
          <LocaleSwitch placement="top-start" />
          <ThemeSwitch placement="top-start" />
          <Button
            variant="ghost"
            size="icon"
            icon={collapsed ? "sidebar-open" : "sidebar-close"}
            title={collapsed ? t("shell.expand") : t("shell.collapse")}
            onClick={onToggle}
          >
            {collapsed ? t("shell.expand") : t("shell.collapse")}
          </Button>
        </div>
      </div>
    </aside>
  )
}
