import { NeedText } from "@/features/need-text"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader } from "@/shared/ui"

export function EmployerNeedTextPage() {
  const { t } = useTranslation("need")
  useDocumentTitle(t("text.title"))
  return (
    <>
      <PageHeader
        title={t("text.title")}
        description={t("text.lead")}
        crumbs={[{ label: t("list.title"), to: "/employer/needs" }]}
      />
      <PageBody>
        <NeedText />
      </PageBody>
    </>
  )
}
