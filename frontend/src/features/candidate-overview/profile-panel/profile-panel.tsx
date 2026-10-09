import { useProfile } from "@/entities/profile"
import type { Profile } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, Meter, Skeleton } from "@/shared/ui"
import styles from "./profile-panel.module.css"

export interface ProfilePanelProps {
  readonly motionIndex?: number
  readonly className?: string | undefined
}

function completeness(profile: Profile | null): number {
  if (profile === null) return 0
  const filled = [
    profile.full_name.trim() !== "",
    profile.contact_email.trim() !== "",
    profile.contact_phone !== null || profile.telegram !== null,
    profile.about.trim() !== "",
    profile.stack.length > 0,
    profile.job_roles.length > 0,
    profile.soft_skills.length > 0,
    profile.work_formats.length > 0,
    profile.city !== null,
    profile.industries.length > 0,
    profile.salary_from > 0,
  ]
  return filled.filter(Boolean).length / filled.length
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
        <ButtonLink to="/candidate/profile" variant="secondary" icon="eye">
          {t("profile.preview")}
        </ButtonLink>
      </div>
    </Card>
  )
}
