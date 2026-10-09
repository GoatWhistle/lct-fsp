import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { FspSection } from "./fsp-section/fsp-section"
import { Hero } from "./hero/hero"
import { HomeFooter } from "./home-footer/home-footer"
import { HowItWorks } from "./how-it-works/how-it-works"
import { Scenarios } from "./scenarios/scenarios"

export function HomePage() {
  const { t } = useTranslation("home")
  useDocumentTitle(t("title"))
  return (
    <main id="main">
      <Hero />
      <HowItWorks />
      <Scenarios />
      <FspSection />
      <HomeFooter />
    </main>
  )
}
