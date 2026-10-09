import { Navigate, useLocation } from "react-router"
import { isRevealState, usePath } from "@/entities/candidate-path"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { TestResult } from "@/features/candidate-path"
import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useDocumentTitle, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, Icon, LoadError, Lockup, Spinner } from "@/shared/ui"
import styles from "./candidate-reveal-page.module.css"

function Reveal({ path, fresh, passed }: { path: CandidatePath; fresh: boolean; passed: boolean }) {
  const { t } = useTranslation("path")
  const names = useCatalogNames()
  const category = path.category
  if (category === null) return null
  const grade = names.grade(category.grade)
  return (
    <div className={styles.page} data-fresh={fresh}>
      <section className={styles.stage} data-surface="inverse" aria-labelledby="reveal-title">
        <Lockup size="sm" />
        <div className={styles.copy}>
          <p className={styles.label} style={staggerStyle(0)}>
            {passed ? t("reveal.label") : t("reveal.notPassedTitle", { grade })}
          </p>
          <svg className={styles.trace} viewBox="0 0 320 24" aria-hidden="true">
            <path className={styles.line} d="M6 12h300" pathLength={1} />
            <circle className={styles.start} cx={6} cy={12} r={5} />
            <circle className={styles.node} cx={308} cy={12} r={7} />
          </svg>
          <h1 id="reveal-title" className={styles.title} tabIndex={-1}>
            <span className={styles.specialization} style={staggerStyle(1)}>
              <Icon name={specializationIcon(category.specialization.code)} size="xl" />
              {names.specialization(category.specialization)}
            </span>
            <span className={styles.grade} style={staggerStyle(2)}>
              <Icon name={gradeIcon(category.grade.code)} size="xl" />
              {grade}
            </span>
          </h1>
          <p className={styles.lead} style={staggerStyle(3)}>
            {passed ? t("reveal.lead") : t("reveal.notPassedText")}
          </p>
          <div className={styles.actions} style={staggerStyle(4)}>
            <ButtonLink to="/candidate" icon="arrow-right" iconPosition="end">
              {t("reveal.toCabinet")}
            </ButtonLink>
          </div>
        </div>
      </section>
      {path.result === null ? null : (
        <aside className={styles.result}>
          <TestResult
            result={path.result}
            highlight={category.grade.code}
            animate={fresh}
            expressLimit={path.express?.limit}
          />
        </aside>
      )}
    </div>
  )
}

export function CandidateRevealPage() {
  const { t } = useTranslation("path")
  const location = useLocation()
  const path = usePath()
  useDocumentTitle(t("reveal.label"))
  const state: unknown = location.state
  const fresh = isRevealState(state)
  const attempted = isRevealState(state) ? state.attempted : null

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
        <Spinner label={t("reveal.label")} />
      </main>
    )
  if (path.data.category === null) return <Navigate to="/candidate/path" replace />

  const passed = attempted === null || attempted === path.data.category.grade.code
  return (
    <main id="main">
      <Reveal path={path.data} fresh={fresh} passed={passed} />
    </main>
  )
}
