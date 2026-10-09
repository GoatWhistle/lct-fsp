import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Hero } from "./hero/hero"

export function HomePage() {
  const { t } = useTranslation("home")
  useDocumentTitle(t("title"))
  return (
    <main id="main">
      <Hero />
    </main>
  )
}
