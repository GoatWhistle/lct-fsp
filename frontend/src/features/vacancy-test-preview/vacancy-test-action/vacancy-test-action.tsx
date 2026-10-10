import { useState } from "react"
import { useTranslation } from "@/shared/i18n"
import { Button, type ButtonSize, Dialog } from "@/shared/ui"
import { VacancyTestPreview } from "../vacancy-test-preview/vacancy-test-preview"

export interface VacancyTestActionProps {
  readonly needId: string
  readonly size?: ButtonSize
}

export function VacancyTestAction({ needId, size = "regular" }: VacancyTestActionProps) {
  const { t } = useTranslation(["vacancyTest", "common"])
  const [open, setOpen] = useState(false)
  const [opened, setOpened] = useState(false)
  return (
    <>
      <Button
        variant="secondary"
        icon="test"
        size={size}
        onClick={() => {
          setOpened(true)
          setOpen(true)
        }}
      >
        {t("action")}
      </Button>
      {opened ? (
        <Dialog
          open={open}
          onClose={() => setOpen(false)}
          title={t("title")}
          size="wide"
          actions={
            <Button variant="ghost" onClick={() => setOpen(false)}>
              {t("common:action.close")}
            </Button>
          }
        >
          <VacancyTestPreview needId={needId} />
        </Dialog>
      ) : null}
    </>
  )
}
