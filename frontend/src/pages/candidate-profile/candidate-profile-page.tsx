import { FspSignIn } from "@/features/auth"
import { FeedbackButton } from "@/features/candidate-overview"
import { FspReturn, PdfButton, ProfileEditor } from "@/features/profile"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader } from "@/shared/ui"

export function CandidateProfilePage() {
  const { t } = useTranslation("profile")
  useDocumentTitle(t("title"))
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("lead")}
        actions={
          <>
            <FeedbackButton />
            <PdfButton />
          </>
        }
      />
      <PageBody>
        <FspReturn />
        <ProfileEditor fspLinkAction={<FspSignIn intent="link" label={t("fsp.link")} />} />
      </PageBody>
    </>
  )
}
