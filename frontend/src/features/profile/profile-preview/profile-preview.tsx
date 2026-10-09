import type { ReactNode } from "react"
import { usePath } from "@/entities/candidate-path"
import { gradeIcon, specializationIcon, useIndustries, useTechnologies } from "@/entities/catalog"
import { GradeRuler } from "@/entities/measure"
import type { HideableField } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Card, Chip, IconLabel, NoValue } from "@/shared/ui"
import type { ProfileDraft } from "../profile-draft"
import { TechnologyYears } from "../technology-years/technology-years"
import styles from "./profile-preview.module.css"

export interface ProfilePreviewProps {
  readonly draft: ProfileDraft
  readonly className?: string | undefined
  readonly framed?: boolean | undefined
}

interface RowProps {
  readonly label: string
  readonly field?: HideableField
  readonly hidden: readonly HideableField[]
  readonly children: ReactNode
}

function Row({ label, field, hidden, children }: RowProps) {
  const { t } = useTranslation("profile")
  const concealed = field !== undefined && hidden.includes(field)
  return (
    <div className={styles.row}>
      <dt className={styles.label}>{label}</dt>
      <dd className={styles.value}>
        <Swap swapKey={concealed ? "hidden" : "shown"} as="div">
          {concealed ? (
            <IconLabel icon="lock" tone="secondary">
              {t("preview.concealed")}
            </IconLabel>
          ) : (
            children
          )}
        </Swap>
      </dd>
    </div>
  )
}

function Chips({ items }: { readonly items: readonly string[] }) {
  if (items.length === 0) return <NoValue />
  return (
    <span className={styles.chips}>
      {items.map((item) => (
        <Chip key={item}>{item}</Chip>
      ))}
    </span>
  )
}

function PreviewBody({ draft }: { readonly draft: ProfileDraft }) {
  const { t } = useTranslation("profile")
  const catalog = useTranslation("catalog").t
  const names = useCatalogNames()
  const path = usePath()
  const technologies = useTechnologies()
  const industries = useIndustries()
  const category = path.data?.category ?? null
  const level = path.data?.profile?.overall ?? null
  const techName = (code: string) =>
    technologies.data?.find((item) => item.code === code)?.name ?? code
  const industryName = (code: string) => {
    const found = industries.data?.find((item) => item.code === code)
    return found === undefined ? code : names.industry(found)
  }
  const rowProps = { hidden: draft.hidden }
  return (
    <>
      <div className={styles.card}>
        <div className={styles.head}>
          <IconLabel icon="profile" className={styles.anon}>
            {t("preview.anonymous")}
          </IconLabel>
          {category === null ? (
            <Chip icon="pending">{t("preview.noCategory")}</Chip>
          ) : (
            <span className={styles.chips}>
              <Chip icon={specializationIcon(category.specialization.code)} tone="accent">
                {names.specialization(category.specialization)}
              </Chip>
              <Chip icon={gradeIcon(category.grade.code)}>{names.grade(category.grade)}</Chip>
            </span>
          )}
        </div>
        {level === null ? null : <GradeRuler level={level} size="inline" caption />}
        <dl className={styles.list}>
          <Row label={t("hideable.stack")} field="stack" {...rowProps}>
            <Chips items={draft.stack.map(techName)} />
          </Row>
          <Row label={t("hideable.experience_years")} field="experience_years" {...rowProps}>
            {draft.experience_years === null ? (
              <NoValue />
            ) : (
              t("preview.years", { count: draft.experience_years })
            )}
          </Row>
          <Row label={t("fields.formats")} {...rowProps}>
            <Chips items={draft.work_formats.map((format) => catalog(`workFormat.${format}`))} />
          </Row>
          <Row label={t("hideable.city")} field="city" {...rowProps}>
            {draft.city.trim() === "" ? <NoValue /> : draft.city}
          </Row>
          <Row label={t("hideable.relocation")} field="relocation" {...rowProps}>
            {draft.relocation ? t("preview.relocationYes") : t("preview.relocationNo")}
          </Row>
          <Row label={t("hideable.industries")} field="industries" {...rowProps}>
            <Chips items={draft.industries.map(industryName)} />
          </Row>
        </dl>
      </div>
      <IconLabel icon="lock" tone="secondary" className={styles.later}>
        {t("preview.later")}
      </IconLabel>
      <TechnologyYears entries={draft.experience} />
    </>
  )
}

export function ProfilePreview({ draft, className, framed = true }: ProfilePreviewProps) {
  const { t } = useTranslation("profile")
  if (!framed)
    return (
      <div className={styles.bare}>
        <PreviewBody draft={draft} />
      </div>
    )
  return (
    <Card title={t("preview.title")} description={t("preview.lead")} className={className}>
      <PreviewBody draft={draft} />
    </Card>
  )
}
