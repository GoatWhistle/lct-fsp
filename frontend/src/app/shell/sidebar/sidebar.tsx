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
  return (
    <aside className={styles.sidebar} data-collapsed={collapsed}>
      <div className={styles.brand}>
        <LockupLink to={CABINET_PATH[user.role]} compact={collapsed} />
      </div>
      <ScrollArea label={t("shell.navigation")} className={styles.scroll}>
        <SidebarNav role={user.role} unread={unread} collapsed={collapsed} />
      </ScrollArea>
      <div className={styles.footer}>
        <div className={styles.prefs}>
          <LocaleSwitch placement="top-start" />
          <ThemeSwitch placement="top-start" />
        </div>
        <div className={styles.account}>
          <AccountMenu user={user} iconOnly={collapsed} className={styles.accountMenu} />
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
