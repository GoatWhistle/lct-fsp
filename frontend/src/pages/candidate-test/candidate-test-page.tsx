import { Navigate, useNavigate } from "react-router"
import { isInProgress, REVEAL_ROUTE, type RevealState, usePath } from "@/entities/candidate-path"
import { TestScreen } from "@/features/test-session"
import type { CandidatePath } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { LoadError, Spinner } from "@/shared/ui"
import styles from "./candidate-test-page.module.css"

const PATH_ROUTE = "/candidate/path"

export function CandidateTestPage() {
  const { t } = useTranslation("test")
  const navigate = useNavigate()
  const path = usePath()
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
  if (!isInProgress(path.data)) return <Navigate to={PATH_ROUTE} replace />

  const attempted = path.data.attempt?.grade ?? null
  const block = path.data.topic_block !== null
  const onFinished = (next: CandidatePath) => {
    if (block || next.stage !== "category") {
      navigate(block ? "/candidate" : PATH_ROUTE, { replace: true, viewTransition: true })
      return
    }
    const state: RevealState = { fresh: true, attempted }
    navigate(REVEAL_ROUTE, { replace: true, state, viewTransition: true })
  }

  return (
    <TestScreen
      path={path.data}
      exitTo={block ? "/candidate" : PATH_ROUTE}
      onFinished={onFinished}
    />
  )
}
