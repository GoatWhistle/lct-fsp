import { type ReactNode, useState } from "react"
import { useProfile } from "@/entities/profile"
import { useSession } from "@/entities/session"
import type { Profile } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, Dialog, LoadError, ScrollArea, Skeleton } from "@/shared/ui"
import { AboutSection } from "../about-section/about-section"
import { ContactsSection } from "../contacts-section/contacts-section"
import { ErrorSummary } from "../error-summary/error-summary"
import { ExpectationsSection } from "../expectations-section/expectations-section"
import { ExperienceSection } from "../experience-section/experience-section"
import { FspSection } from "../fsp-section/fsp-section"
import { LeaveGuard } from "../leave-guard/leave-guard"
import { ProfilePreview } from "../profile-preview/profile-preview"
import { ResumeDrop } from "../resume-drop/resume-drop"
import { SaveBar } from "../save-bar/save-bar"
import { SectionNav } from "../section-nav/section-nav"
import { StackSection } from "../stack-section/stack-section"
import { VisibilitySection } from "../visibility-section/visibility-section"
import styles from "./profile-editor.module.css"
import { useProfileEditor } from "./use-profile-editor"

export interface ProfileEditorProps {
  readonly fspLinkAction: ReactNode
  readonly before?: ReactNode
}

interface EditorFormProps extends ProfileEditorProps {
  readonly profile: Profile | null
  readonly email: string
}

function EditorForm({ profile, email, fspLinkAction, before }: EditorFormProps) {
  const { t } = useTranslation("profile")
  const editor = useProfileEditor(profile, email)
  const [previewing, setPreviewing] = useState(false)
  const section = {
    draft: editor.draft,
    onChange: editor.change,
    errors: editor.errors,
    marks: editor.marks,
  }
  return (
    <div className={styles.editor}>
      <aside className={styles.nav}>
        <SectionNav />
      </aside>
      <div className={styles.form}>
        {before}
        <Button
          variant="secondary"
          icon="eye"
          className={styles.previewToggle}
          onClick={() => setPreviewing(true)}
        >
          {t("preview.title")}
        </Button>
        <ErrorSummary missing={editor.missing} attempts={editor.attempts} />
        <ResumeDrop onParsed={editor.takeResume} parsed={editor.parsed} />
        <AboutSection {...section} />
        <ExperienceSection {...section} />
        <ContactsSection {...section} />
        <StackSection {...section} />
        <ExpectationsSection {...section} />
        <VisibilitySection {...section} />
        <FspSection linkAction={fspLinkAction} />
        <SaveBar
          open={editor.dirty}
          saving={editor.saving}
          missing={editor.missing.length}
          onSave={editor.save}
          onReset={editor.reset}
        />
      </div>
      <aside className={styles.preview}>
        <ScrollArea label={t("preview.title")} surface="canvas" className={styles.previewScroll}>
          <ProfilePreview draft={editor.draft} />
        </ScrollArea>
      </aside>
      <Dialog
        open={previewing}
        onClose={() => setPreviewing(false)}
        title={t("preview.title")}
        description={t("preview.lead")}
      >
        <ProfilePreview draft={editor.draft} framed={false} />
      </Dialog>
      <LeaveGuard when={editor.dirty} />
    </div>
  )
}

export function ProfileEditor({ fspLinkAction, before }: ProfileEditorProps) {
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
    return (
      <div className={styles.editor} aria-hidden="true">
        <Skeleton shape="block" className={styles.navPlaceholder} />
        <Skeleton shape="block" className={styles.placeholder} />
        <Skeleton shape="block" className={styles.previewPlaceholder} />
      </div>
    )
  return (
    <EditorForm
      profile={profile.data}
      email={session.data?.email ?? ""}
      fspLinkAction={fspLinkAction}
      before={before}
    />
  )
}
