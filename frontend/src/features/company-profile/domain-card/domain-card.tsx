import { useState } from "react"
import { useRequestDomainCheck } from "@/entities/company"
import type { Company } from "@/shared/api"
import { useErrorText, useLocale, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, FlagRow, Icon, StatusBadge, TextField } from "@/shared/ui"
import styles from "./domain-card.module.css"

export interface DomainFlagProps {
  readonly company: Company
}

function DomainForm({ company }: DomainFlagProps) {
  const { t } = useTranslation("company")
  const errorText = useErrorText()
  const { locale } = useLocale()
  const request = useRequestDomainCheck()
  const [email, setEmail] = useState(company.contact_email)
  return (
    <div className={styles.form}>
      <div className={styles.row}>
        <TextField
          label={t("domain.email")}
          type="text"
          inputMode="email"
          icon="mail"
          value={email}
          onChange={setEmail}
          placeholder={t("domain.emailPlaceholder")}
          maxLength={320}
          className={styles.email}
        />
        <Button
          icon="send"
          variant="secondary"
          pending={request.isPending}
          pendingLabel={t("domain.sending")}
          disabled={email.trim() === ""}
          onClick={() => request.mutate({ email: email.trim(), locale })}
        >
          {t("domain.send")}
        </Button>
      </div>
      <Swap swapKey={request.status} as="div">
        {request.isSuccess ? (
          <Banner tone="info" icon="mail" title={t("domain.sent", { email: email.trim() })} />
        ) : request.isError ? (
          <Banner tone="critical" title={errorText(request.error)} />
        ) : null}
      </Swap>
    </div>
  )
}

export function DomainFlag({ company }: DomainFlagProps) {
  const { t } = useTranslation("company")
  const [open, setOpen] = useState(false)
  const verified = company.domain_verified && company.verified_domain !== null
  const blocked = company.website === null
  const note = verified
    ? (company.verified_domain ?? "")
    : blocked
      ? t("domain.noWebsiteShort")
      : t("domain.note")
  return (
    <>
      <FlagRow
        mark={<Icon name="verification" size="md" />}
        title={verified ? t("domain.mark") : t("domain.title")}
        note={note}
        active={verified}
        trailing={
          verified ? (
            <StatusBadge tone="positive">{t("fsp.confirmed")}</StatusBadge>
          ) : (
            <Button
              variant={open ? "ghost" : "secondary"}
              size="compact"
              icon={open ? "close" : "verification"}
              disabled={blocked}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {open ? t("domain.cancel") : t("domain.start")}
            </Button>
          )
        }
      />
      {open && !verified ? <DomainForm company={company} /> : null}
    </>
  )
}
