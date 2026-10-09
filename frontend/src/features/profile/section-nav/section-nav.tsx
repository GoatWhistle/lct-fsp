import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { useTranslation } from "@/shared/i18n"
import { Icon, type IconName } from "@/shared/ui"
import type { SectionId } from "../editor-section/editor-section"
import styles from "./section-nav.module.css"

const SECTIONS: readonly { readonly id: SectionId; readonly icon: IconName }[] = [
  { id: "resume", icon: "file" },
  { id: "about", icon: "profile" },
  { id: "experience", icon: "company" },
  { id: "contacts", icon: "mail" },
  { id: "stack", icon: "topic" },
  { id: "expectations", icon: "money" },
  { id: "visibility", icon: "eye" },
  { id: "fsp", icon: "fsp" },
]

const OBSERVER_MARGIN = "-20% 0px -70% 0px"

function useActiveSection(): SectionId {
  const [active, setActive] = useState<SectionId>("resume")
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((entry) => entry.isIntersecting)
        const id = visible?.target.getAttribute("data-section")
        if (id !== null && id !== undefined) setActive(id as SectionId)
      },
      { rootMargin: OBSERVER_MARGIN },
    )
    for (const section of SECTIONS) {
      const element = document.getElementById(section.id)
      if (element !== null) observer.observe(element)
    }
    return () => observer.disconnect()
  }, [])
  return active
}

export function SectionNav() {
  const { t } = useTranslation("profile")
  const active = useActiveSection()
  const listRef = useRef<HTMLDivElement | null>(null)
  const indicatorRef = useRef<HTMLSpanElement | null>(null)
  const placed = useRef(false)

  useLayoutEffect(() => {
    const item = listRef.current?.querySelector<HTMLElement>(`[data-nav="${active}"]`)
    const indicator = indicatorRef.current
    if (item === null || item === undefined || indicator === null) return
    indicator.dataset.instant = String(!placed.current)
    indicator.style.transform = `translateY(${item.offsetTop}px)`
    indicator.style.blockSize = `${item.offsetHeight}px`
    placed.current = true
  }, [active])

  return (
    <nav className={styles.nav} aria-label={t("nav")}>
      <div ref={listRef} className={styles.frame}>
        <span ref={indicatorRef} className={styles.indicator} aria-hidden="true" />
        <ul className={styles.list}>
          {SECTIONS.map((section) => (
            <li key={section.id} data-nav={section.id}>
              <a
                href={`#${section.id}`}
                className={styles.link}
                aria-current={active === section.id ? "location" : undefined}
              >
                <Icon name={section.icon} size="sm" />
                {t(`sections.${section.id}`)}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
