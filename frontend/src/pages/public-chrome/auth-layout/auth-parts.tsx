import type { ReactNode } from "react"
import { ButtonLink } from "@/shared/ui"
import styles from "./auth-layout.module.css"

export function AuthDivider({ children }: { readonly children: ReactNode }) {
  return <p className={styles.divider}>{children}</p>
}

export function AuthHint({ children }: { readonly children: ReactNode }) {
  return <p className={styles.hint}>{children}</p>
}

export function AuthBlock({ children }: { readonly children: ReactNode }) {
  return <div className={styles.block}>{children}</div>
}

export function AuthGroup({ children }: { readonly children: ReactNode }) {
  return <div className={styles.group}>{children}</div>
}

export interface AuthSwitchProps {
  readonly text: string
  readonly to: string
  readonly link: string
}

export function AuthSwitch({ text, to, link }: AuthSwitchProps) {
  return (
    <div className={styles.switch}>
      <p className={styles.switchText}>{text}</p>
      <ButtonLink to={to} variant="secondary" size="compact" icon="arrow-right" iconPosition="end">
        {link}
      </ButtonLink>
    </div>
  )
}
