import { useIndustries, useTechnologies } from "@/entities/catalog"
import type { HideableField } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Chip, Icon, type IconName } from "@/shared/ui"
import type { ProfileDraft } from "../profile-draft"
import styles from "./profile-preview.module.css"

interface Fact {
  readonly key: string
  readonly icon: IconName
  readonly field?: HideableField
  readonly text: string
}

function useFacts(draft: ProfileDraft): readonly Fact[] {
  const { t } = useTranslation("profile")
  const catalog = useTranslation("catalog").t
  const names = useCatalogNames()
  const industries = useIndustries()
  const industryName = (code: string) => {
    const found = industries.data?.find((item) => item.code === code)
    return found === undefined ? code : names.industry(found)
  }
  const facts: (Fact | null)[] = [
    draft.experience_years === null
      ? null
      : {
          key: "years",
          icon: "clock",
          field: "experience_years",
          text: t("preview.years", { count: draft.experience_years }),
        },
    draft.work_formats.length === 0
      ? null
      : {
          key: "formats",
          icon: `format-${draft.work_formats[0] ?? "office"}`,
          text: draft.work_formats.map((format) => catalog(`workFormat.${format}`)).join(", "),
        },
    draft.city.trim() === ""
      ? null
      : { key: "city", icon: "city", field: "city", text: draft.city.trim() },
    {
      key: "relocation",
      icon: "benefit-relocation",
      field: "relocation",
      text: draft.relocation ? t("preview.relocationYes") : t("preview.relocationNo"),
    },
    draft.industries.length === 0
      ? null
      : {
          key: "industries",
          icon: "company",
          field: "industries",
          text: draft.industries.map(industryName).join(", "),
        },
  ]
  return facts.filter((fact): fact is Fact => fact !== null)
}

function Concealed({ field }: { readonly field: HideableField }) {
  const { t } = useTranslation("profile")
  return (
    <>
      <Icon name="lock" size="sm" className={styles.factIcon} />
      {t("preview.concealedField", { field: t(`hideable.${field}`) })}
    </>
  )
}

export function PreviewFacts({ draft }: { readonly draft: ProfileDraft }) {
  const facts = useFacts(draft)
  return (
    <ul className={styles.facts}>
      {facts.map((fact) => {
        const concealed = fact.field !== undefined && draft.hidden.includes(fact.field)
        return (
          <li key={fact.key} className={styles.fact} data-concealed={concealed}>
            {concealed && fact.field !== undefined ? (
              <Concealed field={fact.field} />
            ) : (
              <>
                <Icon name={fact.icon} size="sm" className={styles.factIcon} />
                {fact.text}
              </>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export function PreviewStack({ draft }: { readonly draft: ProfileDraft }) {
  const { t } = useTranslation("profile")
  const technologies = useTechnologies()
  if (draft.stack.length === 0) return null
  if (draft.hidden.includes("stack"))
    return (
      <p className={styles.fact} data-concealed="true">
        <Concealed field="stack" />
      </p>
    )
  const name = (code: string) => technologies.data?.find((item) => item.code === code)?.name ?? code
  return (
    <ul className={styles.chips} aria-label={t("hideable.stack")}>
      {draft.stack.map((code) => (
        <li key={code}>
          <Chip>{name(code)}</Chip>
        </li>
      ))}
    </ul>
  )
}
