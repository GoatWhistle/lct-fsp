import { useState } from "react"
import { CompanyTrustMark, useRequestDomainCheck } from "@/entities/company"
import type { Company } from "@/shared/api"
import { useErrorText, useLocale, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, Card, IconLabel, TextField } from "@/shared/ui"
import styles from "./domain-card.module.css"

export interface DomainCardProps {
  readonly company: Company
}

function suggested(company: Company): string {
  return company.contact_email
}

export function DomainCard({ company }: DomainCardProps) {
  const { t } = useTranslation("company")
  const errorText = useErrorText()
  const { locale } = useLocale()
  const request = useRequestDomainCheck()
  const [email, setEmail] = useState(() => suggested(company))
  const send = () => request.mutate({ email: email.trim(), locale })
  return (
    <Card
      title={t("domain.title")}
      description={t("domain.lead")}
      motionIndex={2}
      actions={<CompanyTrustMark verified={company.domain_verified} />}
    >
      <div className={styles.body}>
        {company.domain_verified && company.verified_domain !== null ? (
          <IconLabel icon="accepted" tone="accent">
            {t("domain.verified", { domain: company.verified_domain })}
          </IconLabel>
        ) : null}
        {company.website === null ? (
          <Banner tone="info" icon="link" title={t("domain.noWebsite")} />
        ) : (
          <div className={styles.row}>
            <TextField
              label={t("domain.email")}
              type="text"
              inputMode="email"
              icon="mail"
              value={email}
              onChange={setEmail}
              hint={t("domain.emailHint")}
              maxLength={320}
            />
            <Button
              icon="send"
              variant="secondary"
              pending={request.isPending}
              pendingLabel={t("domain.sending")}
              disabled={email.trim() === ""}
              onClick={send}
            >
              {t("domain.send")}
            </Button>
          </div>
        )}
        <Swap swapKey={request.status} as="div">
          {request.isSuccess ? (
            <Banner tone="info" icon="mail" title={t("domain.sent", { email: email.trim() })} />
          ) : request.isError ? (
            <Banner tone="critical" title={errorText(request.error)} />
          ) : null}
        </Swap>
      </div>
    </Card>
  )
}
