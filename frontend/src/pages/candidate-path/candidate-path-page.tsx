import { useState } from "react"
import { Navigate, useNavigate } from "react-router"
import { usePath } from "@/entities/candidate-path"
import {
  DirectionStep,
  ExpressStep,
  GradeStep,
  NoCategoryStep,
  OfferStep,
} from "@/features/candidate-path"
import { VerificationCard } from "@/features/test-verification"
import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { ButtonLink, Card, LoadError, PageBody, PageHeader, Skeleton } from "@/shared/ui"
import styles from "./candidate-path-page.module.css"
import { PathTrace } from "./path-trace"

const TEST_ROUTE = "/candidate/test"

function InProgress({ path }: { readonly path: CandidatePath }) {
  const { t } = useTranslation("path")
  const names = useCatalogNames()
  return (
    <Card
      title={t("inProgress.title", { grade: names.grade(path.attempt?.grade ?? "") })}
      description={t("inProgress.text")}
    >
      <div>
        <ButtonLink to={TEST_ROUTE} icon="test">
          {t("inProgress.action")}
        </ButtonLink>
      </div>
    </Card>
  )
}

function StepContent({ path }: { readonly path: CandidatePath }) {
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const toTest = () => navigate(TEST_ROUTE, { viewTransition: true })
  if (path.stage === "survey" || (path.stage === "grade" && (editing || path.survey === null)))
    return (
      <DirectionStep
        current={path.survey?.specialization.code ?? null}
        onCancel={path.survey === null ? undefined : () => setEditing(false)}
      />
    )
  if (path.stage === "grade" && path.survey !== null)
    return (
      <GradeStep
        survey={path.survey}
        onChangeDirection={() => setEditing(true)}
        onStarted={toTest}
      />
    )
  if (path.express?.paused) return <ExpressStep path={path} onContinued={toTest} />
  if (path.stage === "verification") return <VerificationCard path={path} />
  if (path.stage === "offer") return <OfferStep path={path} onStarted={toTest} />
  if (path.stage === "no_category") return <NoCategoryStep path={path} />
  return <InProgress path={path} />
}

export function CandidatePathPage() {
  const { t } = useTranslation("path")
  const path = usePath()
  useDocumentTitle(t("title"))
  if (path.data?.stage === "category" && path.data.topic_block === null)
    return <Navigate to="/candidate" replace />
  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} />
      <PageBody>
        {path.isError ? (
          <LoadError
            error={path.error}
            onRetry={() => void path.refetch()}
            pending={path.isFetching}
          />
        ) : path.data === undefined ? (
          <Skeleton shape="block" />
        ) : (
          <div className={styles.layout}>
            <aside className={styles.trace}>
              <PathTrace path={path.data} />
            </aside>
            <Swap swapKey={path.data.stage} as="div">
              <StepContent path={path.data} />
            </Swap>
          </div>
        )}
      </PageBody>
    </>
  )
}
