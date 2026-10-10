import type { ReactNode } from "react"
import { useIndustries } from "@/entities/catalog"
import type { CompanySize } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, Select, TextArea, TextField } from "@/shared/ui"
import { COMPANY_SIZES, type CompanyField, type CompanyForm } from "../company-form"
import styles from "./about-card.module.css"

export interface CompanyCardProps {
  readonly form: CompanyForm
  readonly error: (field: CompanyField) => string | undefined
  readonly onChange: (patch: Partial<CompanyForm>) => void
  readonly className?: string | undefined
}

export interface AboutCardProps extends CompanyCardProps {
  readonly logo: ReactNode
}

export function AboutCard({ form, error, onChange, logo, className }: AboutCardProps) {
  const { t } = useTranslation("company")
  const names = useCatalogNames()
  const industries = useIndustries()
  return (
    <Card level="section" title={t("sections.about")} motionIndex={0} className={className}>
      <div className={styles.fields}>
        <div className={styles.identity}>
          {logo}
          <div className={styles.names}>
            <TextField
              label={t("fields.name")}
              icon="company"
              autoComplete="organization"
              value={form.name}
              onChange={(name) => onChange({ name })}
              maxLength={200}
              placeholder={t("fields.namePlaceholder")}
              error={error("name")}
              required
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
              required
            />
            <Select<CompanySize>
              label={t("fields.size")}
              value={form.size}
              onChange={(size) => onChange({ size })}
              placeholder={t("fields.sizePlaceholder")}
              options={COMPANY_SIZES.map((size) => ({ value: size, label: t(`sizes.${size}`) }))}
            />
          </div>
        </div>
        <TextArea
          label={t("fields.description")}
          value={form.description}
          onChange={(description) => onChange({ description })}
          maxLength={3000}
          minRows={5}
          className={styles.wide}
          error={error("description")}
          required
        />
      </div>
    </Card>
  )
}
