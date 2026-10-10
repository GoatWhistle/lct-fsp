import { useTranslation } from "@/shared/i18n"
import { Chip } from "@/shared/ui"

export interface CompanyTrustMarkProps {
  readonly verified: boolean
}

export function CompanyTrustMark({ verified }: CompanyTrustMarkProps) {
  const { t } = useTranslation("company")
  if (!verified) return null
  return (
    <Chip icon="verification" tone="accent">
      {t("domain.mark")}
    </Chip>
  )
}
