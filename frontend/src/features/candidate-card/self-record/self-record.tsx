import type { CardSelfReported } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, Chip, IconLabel, NoValue, type TermItem, Terms } from "@/shared/ui"
import styles from "./self-record.module.css"

export interface SelfRecordProps {
  readonly self: CardSelfReported | null
}

function chips(
  values: readonly { code: string; name: string }[] | null,
  name: (ref: { code: string; name: string }) => string,
) {
  if (values === null || values.length === 0) return <NoValue />
  return (
    <span className={styles.chips}>
      {values.map((value) => (
        <Chip key={value.code}>{name(value)}</Chip>
      ))}
    </span>
  )
}

export function SelfRecord({ self }: SelfRecordProps) {
  const { t } = useTranslation(["card", "catalog"])
  const names = useCatalogNames()
  if (self === null) return null
  const relocation =
    self.relocation === null ? (
      <NoValue />
    ) : self.relocation ? (
      t("self.relocationYes")
    ) : (
      t("self.relocationNo")
    )
  const items: TermItem[] = [
    {
      key: "experience",
      label: t("self.experienceLabel"),
      icon: "clock",
      value:
        self.experience_years === null ? (
          <NoValue />
        ) : (
          t("self.experience", { count: self.experience_years })
        ),
    },
    {
      key: "formats",
      prose: true,
      label: t("self.formats"),
      icon: "company",
      value:
        self.work_formats.length === 0 ? (
          <NoValue />
        ) : (
          self.work_formats.map((format) => t(`catalog:workFormat.${format}` as never)).join(", ")
        ),
    },
    {
      key: "city",
      prose: true,
      label: t("self.city"),
      icon: "city",
      value: self.city ?? <NoValue />,
    },
    {
      key: "relocation",
      prose: true,
      label: t("self.relocation"),
      icon: "arrow-right",
      value: relocation,
    },
    {
      key: "industries",
      prose: true,
      label: t("self.industries"),
      icon: "company",
      value: chips(self.industries, names.industry),
    },
    {
      key: "stack",
      prose: true,
      label: t("self.stack"),
      icon: "test",
      value: chips(self.stack, (tech) => tech.name),
    },
  ]
  return (
    <Card title={t("self.title")} description={t("self.lead")}>
      <Terms items={items} />
      {self.hidden.length === 0 ? null : (
        <p className={styles.hidden}>
          <IconLabel icon="eye-off" tone="secondary">
            {t("self.hidden", {
              fields: self.hidden.map((field) => t(`card:hideable.${field}` as never)).join(", "),
            })}
          </IconLabel>
        </p>
      )}
    </Card>
  )
}
