import { useTranslation } from "@/shared/i18n"
import { Lockup } from "@/shared/ui"
import styles from "./home-footer.module.css"

export function HomeFooter() {
  const { t } = useTranslation(["home", "common"])
  return (
    <footer className={styles.footer}>
      <Lockup size="sm" />
      <p className={styles.text}>
        {t("footer.made")}
        <br />
        {t("common:brand.fspFull")}
      </p>
    </footer>
  )
}
