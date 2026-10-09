import { useEffect, useRef } from "react"
import { useTranslation } from "@/shared/i18n"
import { Banner, Icon } from "@/shared/ui"
import type { SectionId } from "../editor-section/editor-section"
import type { DraftField } from "../profile-draft"
import styles from "./error-summary.module.css"

const SECTION_OF: Partial<Record<DraftField, SectionId>> = {
  full_name: "about",
  experience_years: "about",
  contact_email: "contacts",
  work_formats: "expectations",
  city: "expectations",
  salary_from: "expectations",
}

export interface ErrorSummaryProps {
  readonly missing: readonly DraftField[]
  readonly attempts: number
}

export function ErrorSummary({ missing, attempts }: ErrorSummaryProps) {
  const { t } = useTranslation("profile")
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (attempts > 0) ref.current?.focus()
  }, [attempts])
  return (
    <div ref={ref} tabIndex={-1} className={styles.anchor}>
      <Banner
        tone="critical"
        open={missing.length > 0}
        title={t("save.summary", { count: missing.length })}
      >
        <ul className={styles.list}>
          {missing.map((field) => (
            <li key={field}>
              <a href={`#${SECTION_OF[field] ?? "about"}`} className={styles.link}>
                <Icon name="arrow-right" size="sm" />
                {t(`profile:errors.${field}` as never)}
              </a>
            </li>
          ))}
        </ul>
      </Banner>
    </div>
  )
}
