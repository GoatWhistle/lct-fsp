import type { ReactNode } from "react"
import { LocaleSwitch, ThemeSwitch } from "@/features/preferences"
import { useTranslation } from "@/shared/i18n"
import { LockupLink } from "@/shared/ui"
import { BrandArt } from "../brand-art/brand-art"
import styles from "./auth-layout.module.css"

export interface AuthLayoutProps {
  readonly title: string
  readonly children: ReactNode
}

export function AuthLayout({ title, children }: AuthLayoutProps) {
  const { t } = useTranslation("auth")
  return (
    <div className={styles.layout}>
      <aside className={styles.aside} data-surface="inverse">
        <div className={styles.top}>
          <LockupLink to="/" />
          <div className={styles.tools}>
            <LocaleSwitch />
            <ThemeSwitch />
          </div>
        </div>
        <div className={styles.pitch}>
          <p className={styles.pitchTitle}>{t("aside.title")}</p>
          <p className={styles.pitchText}>{t("aside.text")}</p>
        </div>
        <BrandArt className={styles.art} />
      </aside>
      <main id="main" className={styles.main}>
        <section className={styles.panel} aria-labelledby="auth-title">
          <h1 id="auth-title" className={styles.title} tabIndex={-1}>
            {title}
          </h1>
          {children}
        </section>
      </main>
    </div>
  )
}
