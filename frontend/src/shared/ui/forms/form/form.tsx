import { clsx } from "clsx"
import type { FormEvent, ReactNode } from "react"
import styles from "./form.module.css"

export interface FormProps {
  readonly onSubmit: () => void
  readonly className?: string | undefined
  readonly id?: string | undefined
  readonly children: ReactNode
}

export function Form({ onSubmit, className, id, children }: FormProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }
  return (
    <form id={id} className={clsx(styles.form, className)} onSubmit={submit}>
      {children}
    </form>
  )
}
