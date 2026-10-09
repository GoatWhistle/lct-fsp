import { NeedList } from "@/features/need-list"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { ButtonLink, PageBody, PageHeader } from "@/shared/ui"

export function EmployerNeedsPage() {
  const { t } = useTranslation("need")
  useDocumentTitle(t("list.title"))
  return (
    <>
      <PageHeader
        title={t("list.title")}
        description={t("list.lead")}
        actions={
          <>
            <ButtonLink to="/employer/needs/text" variant="secondary" icon="llm">
              {t("list.fromText")}
            </ButtonLink>
            <ButtonLink to="/employer/needs/new" icon="plus">
              {t("list.new")}
            </ButtonLink>
          </>
        }
      />
      <PageBody>
        <NeedList />
      </PageBody>
    </>
  )
}
