import { LOCALES, type Locale, useLocale, useTranslation } from "@/shared/i18n"
import type { Placement } from "@/shared/ui"
import { Flag, type FlagCode, IconLabel, RadioMenuButton } from "@/shared/ui"

const FLAGS: Readonly<Record<Locale, FlagCode>> = { ru: "ru", en: "gb" }

export interface LocaleSwitchProps {
  readonly placement?: Placement | undefined
}

export function LocaleSwitch({ placement }: LocaleSwitchProps) {
  const { t } = useTranslation()
  const { locale, setLocale } = useLocale()
  return (
    <RadioMenuButton
      icon="globe"
      label={t("language.current", { name: t(`language.${locale}`) })}
      legend={t("language.legend")}
      value={locale}
      placement={placement}
      onChange={setLocale}
      options={LOCALES.map((value) => ({
        value,
        content: (
          <IconLabel leading={<Flag code={FLAGS[value]} />}>
            <span lang={value}>{t(`language.${value}`)}</span>
          </IconLabel>
        ),
      }))}
    />
  )
}
