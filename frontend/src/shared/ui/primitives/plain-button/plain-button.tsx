import { clsx } from "clsx"
import type { ComponentPropsWithRef } from "react"
import styles from "./plain-button.module.css"

export type PlainButtonProps = Omit<ComponentPropsWithRef<"button">, "type">

export function PlainButton({ className, children, ...rest }: PlainButtonProps) {
  return (
    <button type="button" className={clsx(styles.plain, className)} {...rest}>
      {children}
    </button>
  )
}
