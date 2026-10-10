import { BackendText, useTranslation } from "@/shared/i18n"
import {
  FspMark,
  Icon,
  IconLabel,
  linkHostname,
  ServiceIcon,
  serviceLabel,
  Tooltip,
} from "@/shared/ui"
import { BENEFITS, type CompanyForm, filledLinks, hostOf } from "../company-form"
import styles from "./company-preview.module.css"

export interface PreviewTrustProps {
  readonly accredited: boolean
  readonly partner: boolean
  readonly verified: boolean
}

export function PreviewTrust({ accredited, partner, verified }: PreviewTrustProps) {
  const { t } = useTranslation("company")
  if (!partner && !accredited && !verified) return null
  return (
    <div className={styles.trust}>
      {partner ? (
        <span className={styles.partner}>
          <FspMark className={styles.partnerMark} />
          {t("preview.partner")}
        </span>
      ) : null}
      {verified ? (
        <IconLabel icon="verification" tone="accent">
          {t("domain.mark")}
        </IconLabel>
      ) : null}
      {accredited ? (
        <IconLabel icon="accredited" tone="secondary">
          {t("preview.accredited")}
        </IconLabel>
      ) : null}
    </div>
  )
}

export function PreviewBenefits({ benefits }: { readonly benefits: readonly string[] }) {
  const { t } = useTranslation("company")
  const known = BENEFITS.filter((benefit) => benefits.includes(benefit))
  if (known.length === 0) return null
  return (
    <ul className={styles.benefits} aria-label={t("preview.benefits")}>
      {known.map((benefit) => (
        <li key={benefit} className={styles.benefit}>
          <Icon name={`benefit-${benefit}`} size="sm" className={styles.benefitIcon} />
          {t(`benefits.${benefit}`)}
        </li>
      ))}
    </ul>
  )
}

function LinkTile({ href, name }: { readonly href: string; readonly name: string }) {
  return (
    <li>
      <Tooltip content={name}>
        <span className={styles.linkItem}>
          <ServiceIcon href={href} />
          <span className="visually-hidden">{name}</span>
        </span>
      </Tooltip>
    </li>
  )
}

export function PreviewContacts({ form }: { readonly form: CompanyForm }) {
  const { t } = useTranslation("company")
  const website = hostOf(form.website)
  const links = filledLinks(form.links).filter((link) => linkHostname(link) !== null)
  const email = form.email.trim()
  const phone = form.phone.trim()
  if (website === "" && links.length === 0 && email === "" && phone === "") return null
  return (
    <footer className={styles.contacts}>
      <div className={styles.reach}>
        {email === "" ? null : (
          <IconLabel icon="mail" tone="secondary">
            <BackendText>{email}</BackendText>
          </IconLabel>
        )}
        {phone === "" ? null : (
          <IconLabel icon="phone" tone="secondary">
            {phone}
          </IconLabel>
        )}
      </div>
      <ul className={styles.links} aria-label={t("preview.links")}>
        {website === "" ? null : <LinkTile href={form.website} name={website} />}
        {links.map((link) => (
          <LinkTile
            key={link}
            href={link}
            name={serviceLabel(link) ?? linkHostname(link) ?? link}
          />
        ))}
      </ul>
    </footer>
  )
}
