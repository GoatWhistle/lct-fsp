import { useQueryClient } from "@tanstack/react-query"
import { Navigate, useNavigate } from "react-router"
import { isInProgress, REVEAL_ROUTE, type RevealState, usePath } from "@/entities/candidate-path"
import { INBOX_KEY } from "@/entities/invitation"
import { TestScreen } from "@/features/test-session"
import type { CandidatePath } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { useLatched } from "@/shared/motion"
import { LoadError, Spinner } from "@/shared/ui"
import styles from "./candidate-test-page.module.css"

const PATH_ROUTE = "/candidate/path"

function invitationRoute(path: CandidatePath | undefined): string | null {
  const vacancy = path?.vacancy_test ?? null
  return vacancy === null ? null : `/candidate/invitations/${vacancy.invitation_id}`
}

export function CandidateTestPage() {
  const { t } = useTranslation("test")
  const navigate = useNavigate()
  const client = useQueryClient()
  const path = usePath()
  const current = invitationRoute(path.data)
  const invitation = useLatched(current, current !== null)
  useDocumentTitle(t("documentTitle"))

  if (path.isError)
    return (
      <main id="main" className={styles.state}>
        <LoadError
          error={path.error}
          onRetry={() => void path.refetch()}
          pending={path.isFetching}
        />
      </main>
    )
  if (path.data === undefined)
    return (
      <main id="main" className={styles.state}>
        <Spinner label={t("loading")} />
      </main>
    )
  if (!isInProgress(path.data)) return <Navigate to={invitation ?? PATH_ROUTE} replace />

  const attempted = path.data.attempt?.grade ?? null
  const block = path.data.topic_block !== null
  const exitTo = current ?? (block ? "/candidate" : PATH_ROUTE)
  const onFinished = (next: CandidatePath) => {
    if (current !== null) void client.invalidateQueries({ queryKey: INBOX_KEY })
    if (current !== null || block || next.stage !== "category") {
      navigate(current !== null || block ? exitTo : PATH_ROUTE, {
        replace: true,
        viewTransition: true,
      })
      return
    }
    const state: RevealState = { fresh: true, attempted }
    navigate(REVEAL_ROUTE, { replace: true, state, viewTransition: true })
  }

  return <TestScreen path={path.data} exitTo={exitTo} onFinished={onFinished} />
}
