import { PROFILE_DIALOG_LINK, useProfile } from "@/entities/profile"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, Meter, Skeleton } from "@/shared/ui"
import { completeness } from "../profile-completeness"
import styles from "./profile-panel.module.css"

export interface ProfilePanelProps {
  readonly motionIndex?: number
  readonly className?: string | undefined
}

export function ProfilePanel({ motionIndex, className }: ProfilePanelProps) {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const profile = useProfile()
  const ratio = profile.data === undefined ? null : completeness(profile.data)
  return (
    <Card title={t("profile.title")} motionIndex={motionIndex} className={className}>
      {ratio === null ? (
        <Skeleton lines={2} />
      ) : (
        <Meter label={t("profile.filled")} value={ratio} valueText={format.percent(ratio)} />
      )}
      <p className={styles.text}>{t("profile.text")}</p>
      <div className={styles.actions}>
        <ButtonLink to={PROFILE_DIALOG_LINK} variant="secondary" icon="eye">
          {t("profile.preview")}
        </ButtonLink>
      </div>
    </Card>
  )
}
