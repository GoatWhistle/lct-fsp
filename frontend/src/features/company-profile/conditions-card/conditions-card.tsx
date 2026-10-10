import type { ReactNode } from "react"
import { useTranslation } from "@/shared/i18n"
import {
  Card,
  ChoiceTiles,
  FlagList,
  FlagRow,
  FspMark,
  Icon,
  StatusBadge,
  Switch,
} from "@/shared/ui"
import type { CompanyCardProps } from "../about-card/about-card"
import { BENEFITS, type Benefit } from "../company-form"
import styles from "./conditions-card.module.css"

export interface ConditionsCardProps extends CompanyCardProps {
  readonly partner: boolean
  readonly domain?: ReactNode
}

export function ConditionsCard({
  form,
  onChange,
  partner,
  domain,
  className,
}: ConditionsCardProps) {
  const { t } = useTranslation("company")
  const toggle = (benefit: Benefit) =>
    onChange({
      benefits: form.benefits.includes(benefit)
        ? form.benefits.filter((item) => item !== benefit)
        : [...form.benefits, benefit],
    })
  return (
    <Card level="section" title={t("sections.conditions")} motionIndex={1} className={className}>
      <div className={styles.fields}>
        <FlagList layout="rows">
          <FlagRow
            mark={<Icon name="accredited" size="md" />}
            title={t("fields.accredited")}
            note={t("fields.accreditedNote")}
            active={form.accredited}
            trailing={
              <Switch
                label={t("fields.accredited")}
                hideLabel
                checked={form.accredited}
                onChange={(accredited) => onChange({ accredited })}
              />
            }
          />
          <FlagRow
            mark={<FspMark className={styles.mark} />}
            title={t("fsp.partner")}
            note={partner ? t("fsp.partnerNote") : t("fsp.none")}
            active={partner}
            trailing={
              <StatusBadge tone={partner ? "positive" : "neutral"}>
                {partner ? t("fsp.confirmed") : t("fsp.missing")}
              </StatusBadge>
            }
          />
          {domain}
        </FlagList>
        <ChoiceTiles<Benefit>
          legend={t("fields.benefits")}
          layout="inline"
          value={null}
          selected={form.benefits.filter((item): item is Benefit =>
            (BENEFITS as readonly string[]).includes(item),
          )}
          onChange={toggle}
          tiles={BENEFITS.map((benefit) => ({
            value: benefit,
            title: t(`benefits.${benefit}`),
            icon: `benefit-${benefit}`,
          }))}
        />
      </div>
    </Card>
  )
}
