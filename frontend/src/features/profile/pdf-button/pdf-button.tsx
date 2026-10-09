import { useDownloadProfilePdf } from "@/entities/profile"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Button, toast } from "@/shared/ui"

export function PdfButton() {
  const { t } = useTranslation("profile")
  const errorText = useErrorText()
  const download = useDownloadProfilePdf()
  return (
    <Button
      variant="secondary"
      icon="download"
      pending={download.isPending}
      pendingLabel={t("pdf.pending")}
      onClick={() =>
        download.mutate(undefined, { onError: (error) => toast.error(errorText(error)) })
      }
    >
      {t("pdf.action")}
    </Button>
  )
}
