import { useMediaQuery } from "@/shared/hooks"
import { useTranslation } from "@/shared/i18n"
import { Section, Trace } from "@/shared/ui"

const STEPS = ["test", "profile", "invite"] as const

export function HowItWorks() {
  const { t } = useTranslation("home")
  const narrow = useMediaQuery("(max-width: 47.99rem)")
  return (
    <Section title={t("how.title")}>
      <Trace
        orientation={narrow ? "vertical" : "horizontal"}
        label={t("how.title")}
        animate
        steps={STEPS.map((step) => ({
          key: step,
          status: "done",
          title: t(`how.${step}.title`),
          description: t(`how.${step}.text`),
        }))}
      />
    </Section>
  )
}
