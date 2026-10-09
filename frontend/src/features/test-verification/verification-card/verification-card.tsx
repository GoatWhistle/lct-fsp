import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router"
import { useSetPath } from "@/entities/candidate-path"
import { api, type CandidatePath, unwrap } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Banner, Button, ButtonLink, Card } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"
import { LowerGrade } from "../lower-grade/lower-grade"

export function VerificationCard({ path }: { readonly path: CandidatePath }) {
  const { t } = useTranslation("test")
  const format = useFormatters()
  const names = useCatalogNames()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const setPath = useSetPath()
  const client = useQueryClient()
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/candidate/path/verification")),
    onSuccess: (next) => {
      client.removeQueries({ queryKey: ["candidate", "path", "item"] })
      setPath(next)
      navigate("/candidate/test", { viewTransition: true })
    },
  })
  const verification = path.verification
  if (!verification) return null
  const last = verification.last
  return (
    <Card title={t("protection.title")} className={styles.enter}>
      <div className={styles.stack}>
        <p>
          {verification.grade
            ? t("protection.required", { grade: names.grade(verification.grade) })
            : t("protection.voluntary")}
        </p>
        {last && !last.confirmed ? (
          <Banner
            tone="attention"
            title={t("protection.mismatch", {
              expected: Math.round(last.expected),
              items: last.items,
              correct: last.correct,
            })}
          />
        ) : null}
        {verification.available_at ? (
          <p>{t("protection.available", { date: format.dateTime(verification.available_at) })}</p>
        ) : null}
        {start.isError ? <Banner tone="critical" title={errorText(start.error)} /> : null}
        <div className={styles.actions}>
          {verification.progress ? (
            <ButtonLink to="/candidate/test" icon="test">
              {t("protection.resume")}
            </ButtonLink>
          ) : (
            <Button
              icon="verification"
              pending={start.isPending}
              disabled={verification.available_at !== null}
              onClick={() => start.mutate()}
            >
              {t("protection.start")}
            </Button>
          )}
        </div>
        {path.stage === "verification" && verification.grade && !verification.progress ? (
          <LowerGrade pending={verification.grade} />
        ) : null}
      </div>
    </Card>
  )
}
