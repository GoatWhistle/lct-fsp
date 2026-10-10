import { usePath } from "@/entities/candidate-path"
import { GradeRuler } from "@/entities/measure"
import { useFspStatus } from "@/entities/profile"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, FspMark, Icon, IconLabel } from "@/shared/ui"
import type { ProfileDraft } from "../profile-draft"
import { TechnologyYears } from "../technology-years/technology-years"
import { PreviewFacts, PreviewStack } from "./preview-facts"
import styles from "./profile-preview.module.css"

export interface ProfilePreviewProps {
  readonly draft: ProfileDraft
  readonly className?: string | undefined
}

function PreviewBody({ draft }: { readonly draft: ProfileDraft }) {
  const { t } = useTranslation("profile")
  const names = useCatalogNames()
  const path = usePath()
  const fsp = useFspStatus()
  const category = path.data?.category ?? null
  const level = path.data?.profile?.overall ?? null
  const achievements = fsp.data?.linked === true ? fsp.data.achievements.length : 0
  return (
    <div className={styles.body}>
      <article className={styles.card}>
        <header className={styles.head}>
          <span className={styles.mark} aria-hidden="true">
            <Icon name="profile" size="md" />
          </span>
          <div className={styles.identity}>
            <p className={styles.name}>{t("preview.anonymous")}</p>
            <p className={styles.meta}>
              {category === null
                ? t("preview.noCategory")
                : `${names.specialization(category.specialization)}, ${names.grade(category.grade)}`}
            </p>
          </div>
        </header>
        {achievements === 0 ? null : (
          <p className={styles.partner}>
            <FspMark />
            {t("preview.fsp", { count: achievements })}
          </p>
        )}
        {level === null ? null : <GradeRuler level={level} size="inline" caption />}
        <PreviewStack draft={draft} />
        <PreviewFacts draft={draft} />
        <TechnologyYears entries={draft.experience} />
      </article>
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("preview.later")}
      </IconLabel>
    </div>
  )
}

export function ProfilePreview({ draft, className }: ProfilePreviewProps) {
  const { t } = useTranslation("profile")
  return (
    <Card level="section" title={t("preview.title")} className={className}>
      <PreviewBody draft={draft} />
    </Card>
  )
}
