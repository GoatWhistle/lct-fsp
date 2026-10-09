import { clsx } from "clsx"
import { type ReactNode, useLayoutEffect, useRef } from "react"
import { Link } from "react-router"
import { Icon } from "../../primitives/icon/icon"
import styles from "./page-header.module.css"

export interface Crumb {
  readonly label: string
  readonly to?: string | undefined
}

export interface PageHeaderProps {
  readonly title: ReactNode
  readonly description?: ReactNode
  readonly crumbs?: readonly Crumb[] | undefined
  readonly actions?: ReactNode
  readonly meta?: ReactNode
  readonly children?: ReactNode
  readonly sticky?: boolean
  readonly className?: string | undefined
}

const STICKY_TOP = "--sticky-top"

function useStickyTop(enabled: boolean) {
  const ref = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const header = ref.current
    if (!enabled || header === null) return
    const root = document.documentElement
    const publish = () => {
      if (getComputedStyle(header).position === "sticky")
        root.style.setProperty(STICKY_TOP, `${header.offsetHeight}px`)
      else root.style.removeProperty(STICKY_TOP)
    }
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(header)
    return () => {
      observer.disconnect()
      root.style.removeProperty(STICKY_TOP)
    }
  }, [enabled])
  return ref
}

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
  meta,
  children,
  sticky = true,
  className,
}: PageHeaderProps) {
  const ref = useStickyTop(sticky)
  return (
    <header ref={ref} className={clsx(styles.header, sticky && styles.sticky, className)}>
      {crumbs !== undefined && crumbs.length > 0 && (
        <nav className={styles.crumbs} aria-label={String(title)}>
          <ol className={styles.crumbList}>
            {crumbs.map((crumb) => (
              <li key={crumb.label} className={styles.crumb}>
                {crumb.to === undefined ? (
                  <span>{crumb.label}</span>
                ) : (
                  <Link to={crumb.to} className={styles.crumbLink} viewTransition>
                    {crumb.label}
                  </Link>
                )}
                <Icon name="chevron-right" size="sm" className={styles.chevron} />
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className={styles.row}>
        <div className={styles.heading}>
          <h1 className={styles.title} tabIndex={-1}>
            {title}
          </h1>
          {meta === undefined ? null : <div className={styles.meta}>{meta}</div>}
          {description === undefined ? null : <p className={styles.description}>{description}</p>}
        </div>
        {actions === undefined ? null : <div className={styles.actions}>{actions}</div>}
      </div>
      {children}
    </header>
  )
}
