import { JuryActions } from "@/features/jury-mode"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink } from "@/shared/ui"
import { PublicBar } from "../../public-chrome/public-bar/public-bar"
import { MapNetwork } from "../map-network/map-network"
import styles from "./hero.module.css"

export function Hero() {
  const { t } = useTranslation(["home", "common"])
  return (
    <section className={styles.hero} aria-labelledby="hero-title">
      <PublicBar showLogin={false} />
      <div className={styles.body}>
        <div className={styles.copy}>
          <h1 id="hero-title" className={styles.title} tabIndex={-1}>
            {t("hero.title")}
          </h1>
          <p className={styles.lead}>{t("hero.lead")}</p>
          <div className={styles.actions}>
            <ButtonLink to="/register?role=candidate">{t("hero.candidate")}</ButtonLink>
            <ButtonLink to="/register?role=employer" variant="dark">
              {t("hero.employer")}
            </ButtonLink>
            <ButtonLink to="/login" variant="secondary" className={styles.signIn}>
              {t("common:action.signIn")}
            </ButtonLink>
          </div>
          <JuryActions className={styles.jury} />
        </div>
        <MapNetwork className={styles.map} />
      </div>
    </section>
  )
}
