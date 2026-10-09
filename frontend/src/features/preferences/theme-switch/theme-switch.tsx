import { useTranslation } from "@/shared/i18n"
import { THEME_CHOICES, type Theme, useTheme } from "@/shared/theme"
import type { IconName, Placement } from "@/shared/ui"
import { IconLabel, RadioMenuButton } from "@/shared/ui"

const CHOICE_ICON: Readonly<Record<Theme, IconName>> = {
  light: "sun",
  dark: "moon",
}

export interface ThemeSwitchProps {
  readonly placement?: Placement | undefined
}

export function ThemeSwitch({ placement }: ThemeSwitchProps) {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  return (
    <RadioMenuButton
      icon={CHOICE_ICON[theme]}
      label={t("theme.current", { name: t(`theme.${theme}`) })}
      legend={t("theme.legend")}
      value={theme}
      placement={placement}
      onChange={setTheme}
      options={THEME_CHOICES.map((value) => ({
        value,
        content: <IconLabel icon={CHOICE_ICON[value]}>{t(`theme.${value}`)}</IconLabel>,
      }))}
    />
  )
}
