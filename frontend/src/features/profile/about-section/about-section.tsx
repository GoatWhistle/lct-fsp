import { useTranslation } from "@/shared/i18n"
import { NumberField, TextArea, TextField } from "@/shared/ui"
import { EditorSection, FieldRow } from "../editor-section/editor-section"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"

const ABOUT_MAX = 2000
const YEARS_MAX = 60

export function AboutSection({ draft, onChange, errors, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  return (
    <EditorSection id="about" title={t("sections.about")}>
      <FieldRow>
        <TextField
          label={t("fields.fullName")}
          icon="profile"
          autoComplete="name"
          value={draft.full_name}
          onChange={(full_name) => onChange({ full_name })}
          hint={hint("full_name")}
          error={errors.full_name}
          required
        />
        <NumberField
          label={t("fields.experience")}
          unit={t("fields.experienceUnit")}
          min={0}
          max={YEARS_MAX}
          value={draft.experience_years}
          onChange={(experience_years) => onChange({ experience_years })}
          hint={hint("experience_years", t("fields.experienceHint"))}
          error={errors.experience_years}
        />
      </FieldRow>
      <TextArea
        label={t("fields.about")}
        value={draft.about}
        onChange={(about) => onChange({ about })}
        maxLength={ABOUT_MAX}
        hint={t("fields.aboutHint")}
        minRows={4}
      />
      <TextField
        label={t("fields.roles")}
        value={draft.job_roles}
        onChange={(job_roles) => onChange({ job_roles })}
        hint={hint("job_roles", t("fields.listHint"))}
      />
      <TextField
        label={t("fields.softSkills")}
        value={draft.soft_skills}
        onChange={(soft_skills) => onChange({ soft_skills })}
        hint={hint("soft_skills", t("fields.listHint"))}
      />
    </EditorSection>
  )
}
