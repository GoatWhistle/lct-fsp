import { useIndustries } from "@/entities/catalog"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, Select, TextArea, TextField } from "@/shared/ui"
import type { CompanyField, CompanyForm } from "../company-form"
import styles from "./about-card.module.css"

export interface CompanyCardProps {
  readonly form: CompanyForm
  readonly error: (field: CompanyField) => string | undefined
  readonly onChange: (patch: Partial<CompanyForm>) => void
  readonly className?: string | undefined
}

export function AboutCard({ form, error, onChange, className }: CompanyCardProps) {
  const { t } = useTranslation("company")
  const names = useCatalogNames()
  const industries = useIndustries()
  return (
    <Card
      title={t("sections.about")}
      description={t("sections.aboutLead")}
      motionIndex={0}
      className={className}
    >
      <div className={styles.fields}>
        <div className={styles.pair}>
          <TextField
            label={t("fields.name")}
            icon="company"
            autoComplete="organization"
            value={form.name}
            onChange={(name) => onChange({ name })}
            maxLength={200}
            placeholder={t("fields.namePlaceholder")}
            error={error("name")}
          />
          <Select
            label={t("fields.industry")}
            value={form.industry}
            onChange={(industry) => onChange({ industry })}
            placeholder={t("fields.industryPlaceholder")}
            options={(industries.data ?? []).map((item) => ({
              value: item.code,
              label: names.industry(item),
            }))}
            error={error("industry")}
          />
        </div>
        <TextArea
          label={t("fields.description")}
          value={form.description}
          onChange={(description) => onChange({ description })}
          maxLength={3000}
          minRows={7}
          hint={t("fields.descriptionHint")}
          error={error("description")}
        />
      </div>
    </Card>
  )
}
