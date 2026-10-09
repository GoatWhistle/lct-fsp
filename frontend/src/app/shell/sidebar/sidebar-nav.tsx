import { clsx } from "clsx"
import { NavLink, useLocation } from "react-router"
import type { Role } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Icon, Tooltip } from "@/shared/ui"
import { NAV_ITEMS, type NavItem } from "../nav-items"
import styles from "./sidebar.module.css"
import { useVerticalIndicator } from "./use-vertical-indicator"

export interface SidebarNavProps {
  readonly role: Role
  readonly unread: number
  readonly collapsed: boolean
}

function isActive(item: NavItem, pathname: string): boolean {
  if (item.end === true) return pathname === item.to || pathname === `${item.to}/path`
  return pathname === item.to || pathname.startsWith(`${item.to}/`)
}

export function SidebarNav({ role, unread, collapsed }: SidebarNavProps) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const items = NAV_ITEMS[role]
  const active = items.find((item) => isActive(item, pathname))?.key ?? null
  const { listRef, indicatorRef } = useVerticalIndicator(active, String(collapsed))

  return (
    <nav className={styles.nav} aria-label={t("shell.navigation")}>
      <ul ref={listRef} className={styles.list}>
        <span ref={indicatorRef} className={styles.indicator} aria-hidden="true" />
        {items.map((item) => {
          const label = t(`nav.${item.key}`)
          const count = item.unread === true ? unread : 0
          const link = (
            <NavLink
              to={item.to}
              end={item.end === true}
              className={clsx(styles.link)}
              aria-current={item.key === active ? "page" : undefined}
            >
              <Icon name={item.icon} size="md" />
              <span className={collapsed ? "visually-hidden" : styles.linkText}>{label}</span>
              {count > 0 && (
                <span className={styles.count}>
                  <span aria-hidden="true">{count}</span>
                  <span className="visually-hidden">{t("shell.unread", { count })}</span>
                </span>
              )}
            </NavLink>
          )
          return (
            <li key={item.key} data-nav={item.key} className={styles.item}>
              {collapsed ? (
                <Tooltip content={label} side="right">
                  {link}
                </Tooltip>
              ) : (
                link
              )}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
