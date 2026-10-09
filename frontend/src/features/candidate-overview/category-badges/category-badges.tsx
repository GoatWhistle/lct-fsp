import { clsx } from "clsx"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import type { Category } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Icon } from "@/shared/ui"
import styles from "./category-badges.module.css"

export interface CategoryBadgesProps {
  readonly category: Category
  readonly size?: "regular" | "large"
  readonly className?: string | undefined
}

export function CategoryBadges({ category, size = "regular", className }: CategoryBadgesProps) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  return (
    <ul
      className={clsx(styles.badges, className)}
      data-size={size}
      aria-label={t("category.label")}
    >
      <li className={styles.badge} data-kind="specialization">
        <Icon name={specializationIcon(category.specialization.code)} size="sm" />
        {names.specialization(category.specialization)}
      </li>
      <li className={styles.badge} data-kind="grade">
        <Icon name={gradeIcon(category.grade.code)} size="sm" />
        {names.grade(category.grade)}
      </li>
    </ul>
  )
}
