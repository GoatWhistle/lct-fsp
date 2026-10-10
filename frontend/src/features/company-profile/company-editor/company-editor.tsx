import { useEffect, useState } from "react"
import { useBlocker } from "react-router"
import { KEEP_LOGO, type LogoChange, useSaveCompany } from "@/entities/company"
import type { Company } from "@/shared/api"
import { useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, ConfirmDialog, Form, IconLabel } from "@/shared/ui"
import { AboutCard } from "../about-card/about-card"
import {
  type CompanyField,
  type CompanyForm,
  companyErrors,
  formOf,
  initialsOf,
  inputOf,
  sameForm,
} from "../company-form"
import { CompanyPreview } from "../company-preview/company-preview"
import { ConditionsCard } from "../conditions-card/conditions-card"
import { ContactsCard } from "../contacts-card/contacts-card"
import { DomainFlag } from "../domain-card/domain-card"
import { LinksCard } from "../links-card/links-card"
import { LogoField, useLogoSource } from "../logo-field/logo-field"
import styles from "./company-editor.module.css"

export interface CompanyEditorProps {
  readonly company: Company | null
  readonly onSaved: (company: Company, created: boolean) => void
  readonly onDirtyChange?: ((dirty: boolean) => void) | undefined
}

function useStatus(company: Company | null, dirty: boolean) {
  const { t } = useTranslation("company")
  const format = useFormatters()
  if (dirty) return { key: "dirty", icon: "edit" as const, text: t("state.dirty") }
  if (company === null) return { key: "new", icon: "pending" as const, text: t("state.new") }
  return {
    key: "saved",
    icon: "check" as const,
    text: t("state.saved", { date: format.date(company.updated_at) }),
  }
}

export function CompanyEditor({ company, onSaved, onDirtyChange }: CompanyEditorProps) {
  const { t } = useTranslation(["company", "common"])
  const errorText = useErrorText()
  const save = useSaveCompany()
  const [base, setBase] = useState<CompanyForm>(() => formOf(company))
  const [form, setForm] = useState<CompanyForm>(base)
  const [tried, setTried] = useState(false)
  const [logo, setLogo] = useState<LogoChange>(KEEP_LOGO)
  const current = company?.logo_url ?? null
  const logoSource = useLogoSource(current, logo)
  const dirty = !sameForm(form, base) || logo.kind !== "keep"
  const blocker = useBlocker(dirty && !save.isPending)
  const status = useStatus(company, dirty)
  const failed = companyErrors(form)
  const error = (field: CompanyField) => (tried && failed[field] ? t(`errors.${field}`) : undefined)
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange])
  const change = (patch: Partial<CompanyForm>) => setForm((current) => ({ ...current, ...patch }))

  const submit = () => {
    setTried(true)
    const input = inputOf(form)
    if (input === null) return
    save.mutate(
      { input, logo },
      {
        onSuccess: (saved) => {
          const next = formOf(saved)
          setBase(next)
          setForm(next)
          setLogo(KEEP_LOGO)
          setTried(false)
          onSaved(saved, company === null)
        },
      },
    )
  }
  const cards = { form, error, onChange: change }

  return (
    <Form onSubmit={submit} className={styles.editor}>
      <div className={styles.fields}>
        <AboutCard
          {...cards}
          logo={
            <LogoField
              current={current}
              source={logoSource}
              initials={initialsOf(form.name.trim())}
              onChange={setLogo}
            />
          }
        />
        <ConditionsCard
          {...cards}
          partner={company?.fsp_partner ?? false}
          domain={company === null ? null : <DomainFlag company={company} />}
        />
        <LinksCard {...cards} />
        <ContactsCard {...cards} />
      </div>
      <CompanyPreview
        form={form}
        logo={logoSource}
        partner={company?.fsp_partner ?? false}
        verified={company?.domain_verified ?? false}
        className={styles.preview}
      />
      <div className={styles.footer}>
        {save.isError ? <Banner tone="critical" title={errorText(save.error)} /> : null}
        <div className={styles.bar}>
          <Swap swapKey={status.key} as="div" className={styles.status}>
            <IconLabel icon={status.icon} tone={dirty ? "accent" : "secondary"}>
              {status.text}
            </IconLabel>
          </Swap>
          <div className={styles.actions}>
            {dirty ? (
              <Button
                variant="ghost"
                icon="retry"
                disabled={save.isPending}
                className={styles.reset}
                onClick={() => {
                  setForm(base)
                  setLogo(KEEP_LOGO)
                }}
              >
                {t("actions.reset")}
              </Button>
            ) : null}
            <Button
              type="submit"
              icon="check"
              disabled={company !== null && !dirty}
              pending={save.isPending}
              pendingLabel={t("actions.saving")}
            >
              {company === null ? t("actions.create") : t("actions.save")}
            </Button>
          </div>
        </div>
      </div>
      <ConfirmDialog
        open={blocker.state === "blocked"}
        title={t("common:leave.title")}
        description={t("common:leave.text")}
        confirmLabel={t("common:leave.leave")}
        cancelLabel={t("common:leave.stay")}
        tone="danger"
        onConfirm={() => blocker.proceed?.()}
        onClose={() => blocker.reset?.()}
      />
    </Form>
  )
}
