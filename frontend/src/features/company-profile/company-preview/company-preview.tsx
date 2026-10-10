import { useIndustries } from "@/entities/catalog"
import { BackendText, useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, Icon, IconLabel } from "@/shared/ui"
import { type CompanyForm, initialsOf } from "../company-form"
import styles from "./company-preview.module.css"
import { PreviewBenefits, PreviewContacts, PreviewTrust } from "./preview-extras"

export interface CompanyPreviewProps {
  readonly form: CompanyForm
  readonly logo: string | null
  readonly partner: boolean
  readonly verified: boolean
  readonly className?: string | undefined
}

function useMeta(form: CompanyForm): string {
  const { t } = useTranslation("company")
  const names = useCatalogNames()
  const industries = useIndustries()
  const industry = industries.data?.find((item) => item.code === form.industry)
  return [
    industry === undefined ? null : names.industry(industry),
    form.size === null ? null : t(`sizes.${form.size}`),
  ]
    .filter((part): part is string => part !== null)
    .join(", ")
}

export function CompanyPreview({ form, logo, partner, verified, className }: CompanyPreviewProps) {
  const { t } = useTranslation("company")
  const meta = useMeta(form)
  const name = form.name.trim()
  const initials = initialsOf(name)
  const description = form.description.trim()
  return (
    <Card level="section" title={t("preview.title")} motionIndex={3} className={className}>
      <article className={styles.card}>
        <header className={styles.head}>
          <span className={styles.mark} aria-hidden="true">
            {logo !== null ? (
              <img className={styles.logo} src={logo} alt="" />
            ) : initials === "" ? (
              <Icon name="company" size="md" />
            ) : (
              initials
            )}
          </span>
          <div className={styles.identity}>
            <p className={styles.name} data-empty={name === ""}>
              {name === "" ? t("preview.untitled") : <BackendText>{name}</BackendText>}
            </p>
            {meta === "" ? null : <p className={styles.meta}>{meta}</p>}
          </div>
        </header>
        <PreviewTrust accredited={form.accredited} partner={partner} verified={verified} />
        <p className={styles.description} data-empty={description === ""}>
          {description === "" ? (
            t("preview.noDescription")
          ) : (
            <BackendText>{description}</BackendText>
          )}
        </p>
        <PreviewBenefits benefits={form.benefits} />
        <PreviewContacts form={form} />
      </article>
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("preview.note")}
      </IconLabel>
    </Card>
  )
}
