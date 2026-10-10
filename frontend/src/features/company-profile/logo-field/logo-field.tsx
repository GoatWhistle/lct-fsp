import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react"
import type { LogoChange } from "@/entities/company"
import { useTranslation } from "@/shared/i18n"
import { Button } from "@/shared/ui"
import styles from "./logo-field.module.css"

const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"]
const LOGO_MAX_BYTES = 512 * 1024

export interface LogoFieldProps {
  readonly current: string | null
  readonly source: string | null
  readonly initials: string
  readonly onChange: (change: LogoChange) => void
}

export function useLogoSource(current: string | null, change: LogoChange): string | null {
  const file = change.kind === "upload" ? change.file : null
  const local = useMemo(() => (file === null ? null : URL.createObjectURL(file)), [file])
  useEffect(() => () => (local === null ? undefined : URL.revokeObjectURL(local)), [local])
  if (change.kind === "remove") return null
  return local ?? current
}

export function LogoField({ current, source, initials, onChange }: LogoFieldProps) {
  const { t } = useTranslation("company")
  const input = useRef<HTMLInputElement>(null)
  const [problem, setProblem] = useState<"logoType" | "logoSize" | null>(null)

  const take = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (file === undefined) return
    if (!LOGO_TYPES.includes(file.type)) return setProblem("logoType")
    if (file.size > LOGO_MAX_BYTES) return setProblem("logoSize")
    setProblem(null)
    onChange({ kind: "upload", file })
  }

  return (
    <div className={styles.field}>
      <span className={styles.label}>{t("fields.logo")}</span>
      <input
        ref={input}
        type="file"
        accept={LOGO_TYPES.join(",")}
        className="visually-hidden"
        tabIndex={-1}
        onChange={take}
      />
      <div className={styles.tile} data-empty={source === null}>
        {source === null ? (
          <span className={styles.initials}>{initials === "" ? null : initials}</span>
        ) : (
          <img className={styles.image} src={source} alt="" />
        )}
        <div className={styles.overlay}>
          <Button
            variant="ghost"
            size="icon"
            icon="image"
            className={styles.action}
            onClick={() => input.current?.click()}
          >
            {source === null ? t("logo.upload") : t("logo.replace")}
          </Button>
          {source === null ? null : (
            <Button
              variant="ghost"
              size="icon"
              icon="trash"
              className={styles.action}
              onClick={() => onChange(current === null ? { kind: "keep" } : { kind: "remove" })}
            >
              {t("logo.remove")}
            </Button>
          )}
        </div>
      </div>
      <span className={styles.hint} data-error={problem !== null}>
        {problem === null ? (
          <>
            <span>{t("logo.formats")}</span>
            <span>{t("logo.limit")}</span>
          </>
        ) : (
          t(`errors.${problem}`)
        )}
      </span>
    </div>
  )
}
