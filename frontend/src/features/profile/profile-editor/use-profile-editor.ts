import { useState } from "react"
import { useSaveProfile } from "@/entities/profile"
import type { Profile, ResumeDraft } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { toast } from "@/shared/ui"
import {
  type DraftErrors,
  type DraftField,
  type DraftPatch,
  draftOf,
  type FieldMark,
  inputOf,
  type ProfileDraft,
  recognizedFields,
  sameDraft,
  validate,
  withResume,
} from "../profile-draft"

export interface ProfileEditorState {
  readonly draft: ProfileDraft
  readonly dirty: boolean
  readonly errors: DraftErrors
  readonly missing: readonly DraftField[]
  readonly attempts: number
  readonly marks: ReadonlyMap<string, FieldMark>
  readonly parsed: ResumeDraft | null
  readonly saving: boolean
  readonly change: (patch: DraftPatch) => void
  readonly takeResume: (parsed: ResumeDraft) => void
  readonly save: () => void
  readonly reset: () => void
}

function marksOf(parsed: ResumeDraft): ReadonlyMap<string, FieldMark> {
  return new Map(
    recognizedFields(parsed).map((field) => [
      field,
      parsed.uncertain.includes(field) ? "uncertain" : "recognized",
    ]),
  )
}

const NO_MARKS: ReadonlyMap<string, FieldMark> = new Map()

function useErrorMessages(missing: readonly DraftField[], shown: boolean): DraftErrors {
  const { t } = useTranslation("profile")
  if (!shown) return {}
  const errors: Partial<Record<DraftField, string>> = {}
  for (const field of missing) errors[field] = t(`profile:errors.${field}` as never)
  return errors
}

export function useProfileEditor(profile: Profile | null, email: string): ProfileEditorState {
  const { t } = useTranslation("profile")
  const errorText = useErrorText()
  const saveProfile = useSaveProfile()
  const [base, setBase] = useState(() => draftOf(profile, email))
  const [draft, setDraft] = useState(base)
  const [marks, setMarks] = useState(NO_MARKS)
  const [parsed, setParsed] = useState<ResumeDraft | null>(null)
  const [attempted, setAttempted] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const missing = validate(draft)
  const errors = useErrorMessages(missing, attempted)

  const save = () => {
    setAttempted(true)
    if (missing.length > 0) {
      setAttempts((count) => count + 1)
      return
    }
    saveProfile.mutate(inputOf(draft), {
      onSuccess: (saved) => {
        const next = draftOf(saved, email)
        setBase(next)
        setDraft(next)
        setMarks(NO_MARKS)
        setParsed(null)
        setAttempted(false)
        toast.success(t("save.done"))
      },
      onError: (error) => toast.error(errorText(error)),
    })
  }

  return {
    draft,
    dirty: !sameDraft(draft, base),
    errors,
    missing: attempted ? missing : [],
    attempts,
    marks,
    parsed,
    saving: saveProfile.isPending,
    change: (patch) => setDraft((current) => ({ ...current, ...patch })),
    takeResume: (next) => {
      setDraft((current) => withResume(current, next))
      setMarks(marksOf(next))
      setParsed(next)
    },
    save,
    reset: () => {
      setDraft(base)
      setMarks(NO_MARKS)
      setParsed(null)
      setAttempted(false)
    },
  }
}
