import type { ReactNode } from "react"
import { LocaleSwitch, ThemeSwitch } from "@/features/preferences"
import { LockupLink } from "@/shared/ui"
import { BrandArt } from "../brand-art/brand-art"
import styles from "./auth-layout.module.css"

export interface AuthLayoutProps {
  readonly title: string
  readonly children: ReactNode
}

export function AuthLayout({ title, children }: AuthLayoutProps) {
  return (
    <div className={styles.layout}>
      <aside className={styles.aside}>
        <div className={styles.top}>
          <LockupLink to="/" />
          <div className={styles.tools}>
            <LocaleSwitch />
            <ThemeSwitch />
          </div>
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
