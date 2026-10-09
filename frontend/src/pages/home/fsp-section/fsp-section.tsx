import { FspSignIn } from "@/features/auth"
import { useTranslation } from "@/shared/i18n"
import { FspMark, Section } from "@/shared/ui"
import styles from "./fsp-section.module.css"

export function FspSection() {
  const { t } = useTranslation("home")
  return (
    <Section
      tone="inverse"
      className={styles.section}
      title={
        <span className={styles.heading}>
          <FspMark className={styles.mark} />
          {t("fsp.title")}
        </span>
      }
      lead={t("fsp.text")}
    >
      <img className={styles.map} src="/brand/map.webp" alt="" width={471} height={312} />
      <div className={styles.actions}>
        <FspSignIn variant="primary" label={t("fsp.cta")} />
        <p className={styles.note}>{t("fsp.note")}</p>
      </div>
    </Section>
  )
}
