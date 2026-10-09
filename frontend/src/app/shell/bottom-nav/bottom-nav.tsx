import { clsx } from "clsx"
import { NavLink, useNavigate } from "react-router"
import type { Role } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Icon, Menu } from "@/shared/ui"
import { NAV_ITEMS } from "../nav-items"
import styles from "./bottom-nav.module.css"

const VISIBLE = 4

export interface BottomNavProps {
  readonly role: Role
  readonly unread: number
}

export function BottomNav({ role, unread }: BottomNavProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const items = NAV_ITEMS[role]
  const visible = items.length > VISIBLE + 1 ? items.slice(0, VISIBLE) : items
  const rest = items.slice(visible.length)
  return (
    <nav className={styles.bar} aria-label={t("shell.navigation")}>
      {visible.map((item) => (
        <NavLink
          key={item.key}
          to={item.to}
          end={item.end === true}
          className={clsx(styles.link)}
          viewTransition
        >
          <span className={styles.glyph}>
            <Icon name={item.icon} size="md" />
            {item.unread === true && unread > 0 && (
              <span className={styles.dot}>
                <span className="visually-hidden">{t("shell.unread", { count: unread })}</span>
              </span>
            )}
          </span>
          <span className={styles.label}>{t(`navShort.${item.key}`)}</span>
        </NavLink>
      ))}
      {rest.length > 0 && (
        <div className={styles.more}>
          <Menu
            label={t("action.more")}
            iconOnly
            placement="top-end"
            items={rest.map((item) => ({
              id: item.key,
              label: t(`nav.${item.key}`),
              icon: item.icon,
              onSelect: () => navigate(item.to),
            }))}
          />
        </div>
      )}
    </nav>
  )
}
