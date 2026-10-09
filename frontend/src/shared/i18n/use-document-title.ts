import { useEffect } from "react"
import { useTranslation } from "react-i18next"

export function useDocumentTitle(page: string | null): void {
  const { t } = useTranslation()
  useEffect(() => {
    document.title = page === null ? t("app.documentTitle") : t("app.pageTitle", { page })
  }, [page, t])
}
