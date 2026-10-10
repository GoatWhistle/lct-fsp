import { useCallback, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router"
import { COMPANY_PARAM, useCompany } from "@/entities/company"
import type { Company } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Banner, ConfirmDialog, Dialog, LoadError, Skeleton, toast } from "@/shared/ui"
import { CompanyEditor } from "../company-editor/company-editor"
import styles from "./company-dialog.module.css"

function CompanyBody({
  onSaved,
  onDirtyChange,
}: {
  readonly onSaved: (company: Company, created: boolean) => void
  readonly onDirtyChange: (dirty: boolean) => void
}) {
  const { t } = useTranslation("company")
  const company = useCompany()
  if (company.isError)
    return (
      <LoadError
        error={company.error}
        onRetry={() => void company.refetch()}
        pending={company.isFetching}
      />
    )
  if (company.data === undefined) return <Skeleton shape="block" />
  return (
    <div className={styles.body}>
      {company.data === null ? <Banner tone="info" icon="company" title={t("missing")} /> : null}
      <CompanyEditor company={company.data} onSaved={onSaved} onDirtyChange={onDirtyChange} />
    </div>
  )
}

export function CompanyDialog() {
  const { t } = useTranslation(["company", "common"])
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const open = params.has(COMPANY_PARAM)
  const dirty = useRef(false)
  const [confirming, setConfirming] = useState(false)

  const close = useCallback(() => {
    dirty.current = false
    setConfirming(false)
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete(COMPANY_PARAM)
        return next
      },
      { replace: true },
    )
  }, [setParams])

  const requestClose = () => (dirty.current ? setConfirming(true) : close())

  const onSaved = (_saved: Company, created: boolean) => {
    close()
    if (!created) return void toast.success(t("toast.saved"))
    toast.success(t("toast.created"), {
      label: t("toast.toVacancies"),
      onAction: () => navigate("/employer/vacancies", { viewTransition: true }),
    })
  }

  const onDirtyChange = useCallback((next: boolean) => {
    dirty.current = next
  }, [])

  return (
    <>
      <Dialog open={open} onClose={requestClose} title={t("title")} size="sheet">
        <CompanyBody onSaved={onSaved} onDirtyChange={onDirtyChange} />
      </Dialog>
      <ConfirmDialog
        open={confirming}
        title={t("common:leave.title")}
        description={t("common:leave.text")}
        confirmLabel={t("common:leave.leave")}
        cancelLabel={t("common:leave.stay")}
        tone="danger"
        onConfirm={close}
        onClose={() => setConfirming(false)}
      />
    </>
  )
}
