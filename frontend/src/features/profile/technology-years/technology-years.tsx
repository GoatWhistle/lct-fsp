import { useTechnologies } from "@/entities/catalog"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { type ExperienceDraft, technologyYears } from "../experience"
import styles from "./technology-years.module.css"

export interface TechnologyYearsProps {
  readonly entries: readonly ExperienceDraft[]
}

export function TechnologyYears({ entries }: TechnologyYearsProps) {
  const { t } = useTranslation("profile")
  const format = useFormatters()
  const technologies = useTechnologies()
  const years = technologyYears(entries)
  if (years.length === 0) return null
  const name = (code: string) => technologies.data?.find((item) => item.code === code)?.name ?? code
  return (
    <section className={styles.block} aria-label={t("preview.yearsTitle")}>
      <p className={styles.title}>{t("preview.yearsTitle")}</p>
      <ul className={styles.list}>
        {years.map((item, index) => (
          <li key={item.code} className={styles.item} style={staggerStyle(index)}>
            <span>{name(item.code)}</span>
            <span className={styles.years}>
              {t("preview.techYears", { count: item.years, value: format.number(item.years) })}
            </span>
          </li>
        ))}
      </ul>
      <p className={styles.note}>{t("preview.yearsNote")}</p>
    </section>
  )
}
