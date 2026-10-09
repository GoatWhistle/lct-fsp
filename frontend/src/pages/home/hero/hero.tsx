import { Link } from "react-router"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink } from "@/shared/ui"
import { BrandArt } from "../../public-chrome/brand-art/brand-art"
import { PublicBar } from "../../public-chrome/public-bar/public-bar"
import styles from "./hero.module.css"

export function Hero() {
  const { t } = useTranslation("home")
  return (
    <section className={styles.hero} data-surface="inverse" aria-labelledby="hero-title">
      <PublicBar />
      <div className={styles.body}>
        <div className={styles.copy}>
          <h1 id="hero-title" className={styles.title} tabIndex={-1}>
            {t("hero.title")}
          </h1>
          <p className={styles.lead}>{t("hero.lead")}</p>
          <div className={styles.actions}>
            <ButtonLink to="/register?role=candidate" icon="arrow-right" iconPosition="end">
              {t("hero.candidate")}
            </ButtonLink>
            <ButtonLink to="/register?role=employer" variant="secondary">
              {t("hero.employer")}
            </ButtonLink>
          </div>
          <p className={styles.login}>
            {t("hero.haveAccount")}{" "}
            <Link to="/login" className={styles.loginLink} viewTransition>
              {t("hero.login")}
            </Link>
          </p>
        </div>
        <BrandArt className={styles.heroArt} />
      </div>
    </section>
  )
}
