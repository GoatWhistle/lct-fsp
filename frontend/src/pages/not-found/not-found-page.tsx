import { CABINET_PATH, useSession } from "@/entities/session"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { ButtonLink } from "@/shared/ui"
import { PublicBar } from "../public-chrome/public-bar/public-bar"
import styles from "./not-found-page.module.css"

export function NotFoundPage() {
  const { t } = useTranslation()
  const session = useSession()
  const user = session.data ?? null
  useDocumentTitle(t("notFound.title"))
  return (
    <main id="main" className={styles.page}>
      <PublicBar showLogin={user === null} />
      <section className={styles.body} aria-labelledby="not-found-title">
        <svg className={styles.trace} viewBox="0 0 240 80" aria-hidden="true">
          <path
            className={styles.line}
            d="M8 64h72a24 24 0 0 0 24-24V24a16 16 0 0 1 16-16h40"
            pathLength={1}
          />
          <circle className={styles.node} cx={8} cy={64} r={5} />
          <circle className={styles.end} cx={170} cy={8} r={6} />
        </svg>
        <h1 id="not-found-title" className={styles.title} tabIndex={-1}>
          {t("notFound.title")}
        </h1>
        <p className={styles.text}>{t("notFound.text")}</p>
        <ButtonLink to={user === null ? "/" : CABINET_PATH[user.role]} icon="arrow-left">
          {user === null ? t("notFound.home") : t("notFound.cabinet")}
        </ButtonLink>
      </section>
    </main>
  )
}
