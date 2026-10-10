import { type ReactNode, useEffect } from "react"
import { useProfile } from "@/entities/profile"
import { useSession } from "@/entities/session"
import type { Profile } from "@/shared/api"
import { LoadError, Skeleton } from "@/shared/ui"
import { AboutSection } from "../about-section/about-section"
import { ContactsSection } from "../contacts-section/contacts-section"
import { ErrorSummary } from "../error-summary/error-summary"
import { ExpectationsSection } from "../expectations-section/expectations-section"
import { ExperienceSection } from "../experience-section/experience-section"
import { FspSection } from "../fsp-section/fsp-section"
import { LeaveGuard } from "../leave-guard/leave-guard"
import { PdfButton } from "../pdf-button/pdf-button"
import { ProfilePreview } from "../profile-preview/profile-preview"
import { ResumeDrop } from "../resume-drop/resume-drop"
import { SaveBar } from "../save-bar/save-bar"
import { StackSection } from "../stack-section/stack-section"
import { VisibilitySection } from "../visibility-section/visibility-section"
import styles from "./profile-editor.module.css"
import { useProfileEditor } from "./use-profile-editor"

export interface ProfileEditorProps {
  readonly fspLinkAction: ReactNode
  readonly focus?: "fsp" | null | undefined
  readonly onSaved?: (() => void) | undefined
  readonly onDirtyChange?: ((dirty: boolean) => void) | undefined
}

interface EditorFormProps extends ProfileEditorProps {
  readonly profile: Profile | null
  readonly email: string
}

function EditorForm({
  profile,
  email,
  fspLinkAction,
  focus,
  onSaved,
  onDirtyChange,
}: EditorFormProps) {
  const editor = useProfileEditor(profile, email, onSaved)
  const section = {
    draft: editor.draft,
    onChange: editor.change,
    errors: editor.errors,
    marks: editor.marks,
  }
  useEffect(() => onDirtyChange?.(editor.dirty), [editor.dirty, onDirtyChange])
  useEffect(() => {
    if (focus === "fsp") document.getElementById("fsp")?.scrollIntoView({ block: "start" })
  }, [focus])
  return (
    <div className={styles.editor}>
      <div className={styles.form}>
        <ErrorSummary missing={editor.missing} attempts={editor.attempts} />
        <ResumeDrop onParsed={editor.takeResume} parsed={editor.parsed} />
        <AboutSection {...section} />
        <ExperienceSection {...section} />
        <ContactsSection {...section} />
        <StackSection {...section} />
        <ExpectationsSection {...section} />
        <VisibilitySection {...section} />
        <FspSection linkAction={fspLinkAction} />
      </div>
      <ProfilePreview draft={editor.draft} className={styles.preview} />
      <SaveBar
        dirty={editor.dirty}
        created={profile !== null}
        saving={editor.saving}
        missing={editor.missing.length}
        onSave={editor.save}
        onReset={editor.reset}
        extra={profile === null ? null : <PdfButton />}
        className={styles.footer}
      />
      <LeaveGuard when={editor.dirty} />
    </div>
  )
}

export function ProfileEditor(props: ProfileEditorProps) {
  const profile = useProfile()
  const session = useSession()
  if (profile.isError)
    return (
      <LoadError
        error={profile.error}
        onRetry={() => void profile.refetch()}
        pending={profile.isFetching}
      />
    )
  if (profile.data === undefined || session.data === undefined)
    return <Skeleton shape="block" className={styles.placeholder} />
  return <EditorForm {...props} profile={profile.data} email={session.data?.email ?? ""} />
}
