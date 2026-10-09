import { useState } from "react"
import { useTechnologies } from "@/entities/catalog"
import { BackendText, useLocale, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, Chip, EmptyState, IconLabel } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import { EntryDrawer } from "../entry-drawer/entry-drawer"
import { ENTRIES_MAX, type ExperienceDraft, emptyEntry } from "../experience"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"
import styles from "./experience-section.module.css"

function useMonthLabel(): (month: string) => string {
  const { locale } = useLocale()
  const format = new Intl.DateTimeFormat(locale, { month: "2-digit", year: "numeric" })
  return (month) => {
    const [year, number] = month.split("-").map(Number)
    return format.format(new Date(year ?? 2000, (number ?? 1) - 1, 1))
  }
}

interface EntryRowProps {
  readonly entry: ExperienceDraft
  readonly index: number
  readonly onEdit: () => void
  readonly onRemove: () => void
}

function EntryRow({ entry, index, onEdit, onRemove }: EntryRowProps) {
  const { t } = useTranslation("profile")
  const technologies = useTechnologies()
  const month = useMonthLabel()
  const name = (code: string) => technologies.data?.find((item) => item.code === code)?.name ?? code
  const period =
    entry.end === ""
      ? t("experience.periodOpen", { start: month(entry.start) })
      : t("experience.period", { start: month(entry.start), end: month(entry.end) })
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.main}>
        <BackendText className={styles.place}>{entry.place}</BackendText>
        {entry.role === "" ? null : <BackendText className={styles.role}>{entry.role}</BackendText>}
        <IconLabel icon="calendar" tone="secondary" size="sm">
          {period}
        </IconLabel>
        {entry.stack.length === 0 ? null : (
          <span className={styles.stack}>
            {entry.stack.map((code) => (
              <Chip key={code}>{name(code)}</Chip>
            ))}
          </span>
        )}
      </div>
      <div className={styles.actions}>
        <Button variant="ghost" size="icon" icon="edit" onClick={onEdit}>
          {t("experience.edit", { place: entry.place })}
        </Button>
        <Button variant="ghost" size="icon" icon="trash" onClick={onRemove}>
          {t("experience.remove", { place: entry.place })}
        </Button>
      </div>
    </li>
  )
}

export function ExperienceSection({ draft, onChange, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  const [editing, setEditing] = useState<ExperienceDraft | null>(null)
  const entries = draft.experience
  const isNew = editing !== null && !entries.some((item) => item.key === editing.key)
  const save = (entry: ExperienceDraft) => {
    onChange({
      experience: isNew
        ? [...entries, entry]
        : entries.map((item) => (item.key === entry.key ? entry : item)),
    })
    setEditing(null)
  }
  const note = hint("experience", t("experience.note"))
  return (
    <EditorSection
      id="experience"
      title={t("sections.experience")}
      description={t("experience.lead")}
      actions={
        entries.length < ENTRIES_MAX ? (
          <Button
            variant="secondary"
            size="compact"
            icon="plus"
            onClick={() => setEditing(emptyEntry())}
          >
            {t("experience.add")}
          </Button>
        ) : undefined
      }
    >
      {entries.length === 0 ? (
        <EmptyState
          icon="company"
          title={t("experience.emptyTitle")}
          description={t("experience.emptyText")}
        />
      ) : (
        <ul className={styles.list}>
          {entries.map((entry, index) => (
            <EntryRow
              key={entry.key}
              entry={entry}
              index={index}
              onEdit={() => setEditing(entry)}
              onRemove={() =>
                onChange({ experience: entries.filter((item) => item.key !== entry.key) })
              }
            />
          ))}
        </ul>
      )}
      <IconLabel icon={marks.has("experience") ? "alert" : "info"} tone="secondary" size="sm">
        {note}
      </IconLabel>
      <EntryDrawer entry={editing} isNew={isNew} onSave={save} onClose={() => setEditing(null)} />
    </EditorSection>
  )
}
