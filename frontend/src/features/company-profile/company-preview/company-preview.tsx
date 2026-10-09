import { useIndustries } from "@/entities/catalog"
import { BackendText, useCatalogNames, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Card, Chip, Icon, IconLabel, NoValue, Terms } from "@/shared/ui"
import { type CompanyForm, hostOf, initialsOf } from "../company-form"
import styles from "./company-preview.module.css"

export interface CompanyPreviewProps {
  readonly form: CompanyForm
  readonly className?: string | undefined
}

function valueOr(text: string) {
  const trimmed = text.trim()
  return trimmed === "" ? <NoValue /> : <BackendText>{trimmed}</BackendText>
}

export function CompanyPreview({ form, className }: CompanyPreviewProps) {
  const { t } = useTranslation("company")
  const names = useCatalogNames()
  const industries = useIndustries()
  const industry = industries.data?.find((item) => item.code === form.industry)
  const name = form.name.trim()
  const initials = initialsOf(name)
  const description = form.description.trim()
  const website = hostOf(form.website)
  return (
    <Card
      as="aside"
      title={t("preview.title")}
      description={t("preview.lead")}
      motionIndex={2}
      className={className}
    >
      <div className={styles.frame}>
        <IconLabel icon="invitation" tone="secondary" className={styles.eyebrow}>
          {t("preview.invitation")}
        </IconLabel>
        <div className={styles.head}>
          <span className={styles.mark} aria-hidden="true">
            {initials === "" ? <Icon name="company" size="md" /> : initials}
          </span>
          <div className={styles.identity}>
            <p className={styles.name} data-empty={name === ""}>
              {name === "" ? t("preview.untitled") : <BackendText>{name}</BackendText>}
            </p>
            <Swap swapKey={industry?.code ?? "none"} as="div">
              {industry === undefined ? (
                <NoValue />
              ) : (
                <Chip icon="company" tone="accent">
                  {names.industry(industry)}
                </Chip>
              )}
            </Swap>
          </div>
        </div>
        <p className={styles.description} data-empty={description === ""}>
          {description === "" ? (
            t("preview.noDescription")
          ) : (
            <BackendText>{description}</BackendText>
          )}
        </p>
        <Terms
          className={styles.terms}
          items={[
            {
              key: "website",
              label: t("preview.website"),
              icon: "link",
              value: website === "" ? <NoValue /> : <span className={styles.link}>{website}</span>,
            },
            { key: "email", label: t("preview.email"), icon: "mail", value: valueOr(form.email) },
            { key: "phone", label: t("preview.phone"), icon: "phone", value: valueOr(form.phone) },
          ]}
        />
      </div>
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("preview.note")}
      </IconLabel>
    </Card>
  )
}
