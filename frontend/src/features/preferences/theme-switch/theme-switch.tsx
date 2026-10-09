import { useTranslation } from "@/shared/i18n"
import { THEME_CHOICES, type ThemeChoice, useTheme } from "@/shared/theme"
import type { IconName, Placement } from "@/shared/ui"
import { IconLabel, RadioMenuButton } from "@/shared/ui"

const CHOICE_ICON: Readonly<Record<ThemeChoice, IconName>> = {
  light: "sun",
  dark: "moon",
  system: "monitor",
}

export interface ThemeSwitchProps {
  readonly placement?: Placement | undefined
}

export function ThemeSwitch({ placement }: ThemeSwitchProps) {
  const { t } = useTranslation()
  const { choice, theme, setChoice } = useTheme()
  return (
    <RadioMenuButton
      icon={theme === "dark" ? "moon" : "sun"}
      label={t("theme.current", { name: t(`theme.${choice}`) })}
      legend={t("theme.legend")}
      value={choice}
      placement={placement}
      onChange={setChoice}
      options={THEME_CHOICES.map((value) => ({
        value,
        content: <IconLabel icon={CHOICE_ICON[value]}>{t(`theme.${value}`)}</IconLabel>,
      }))}
    />
  )
}
