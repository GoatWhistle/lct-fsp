import { useLocation, useNavigate, useParams } from "react-router"
import { useNeed } from "@/entities/need"
import { EMPTY_FORM, formFromDraft, formFromNeed, NeedEditor } from "@/features/need-editor"
import type { NeedDraft } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Banner, LoadError, PageBody, PageHeader, Skeleton, toast } from "@/shared/ui"

interface DraftState {
  readonly draft: NeedDraft
}

function draftOf(state: unknown): NeedDraft | null {
  return typeof state === "object" && state !== null && "draft" in state
    ? (state as DraftState).draft
    : null
}

export function EmployerNeedEditorPage() {
  const { t } = useTranslation(["need", "common"])
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const need = useNeed(id)
  const draft = draftOf(location.state)
  const title =
    id === undefined ? t("editor.titleNew") : (need.data?.title ?? t("editor.titleEdit"))
  useDocumentTitle(title)

  const onSaved = () => {
    toast.success(t("editor.saved"))
    navigate("/employer/needs", { viewTransition: true })
  }
  const onBuilt = (selectionId: string) =>
    navigate(`/employer/selections/${selectionId}`, { viewTransition: true })

  const body = () => {
    if (id === undefined)
      return (
        <NeedEditor
          needId={null}
          initial={draft === null ? EMPTY_FORM : formFromDraft(draft)}
          uncertain={new Set(draft?.uncertain ?? [])}
          onSaved={onSaved}
          onBuilt={(selection) => onBuilt(selection.id)}
        />
      )
    if (need.isError)
      return (
        <LoadError
          error={need.error}
          onRetry={() => void need.refetch()}
          pending={need.isFetching}
        />
      )
    if (need.data === undefined) return <Skeleton shape="block" />
    return (
      <NeedEditor
        key={need.data.id}
        needId={need.data.id}
        initial={formFromNeed(need.data)}
        onSaved={onSaved}
        onBuilt={(selection) => onBuilt(selection.id)}
      />
    )
  }

  return (
    <>
      <PageHeader
        title={title}
        description={t("editor.lead")}
        crumbs={[{ label: t("list.title"), to: "/employer/needs" }]}
      />
      <PageBody>
        {draft === null ? null : <Banner tone="info" icon="llm" title={t("editor.fromDraft")} />}
        {body()}
      </PageBody>
    </>
  )
}
