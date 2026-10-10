import { useNavigate, useParams } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { anonymousId, useBuildSelection, useSelection } from "@/entities/selection"
import { InviteAction } from "@/features/invite"
import { SelectionBoard } from "@/features/selection-board"
import { VacancyTestAction } from "@/features/vacancy-test-preview"
import type { NeedDraft, Selection } from "@/shared/api"
import {
  useCatalogNames,
  useDocumentTitle,
  useErrorText,
  useFormatters,
  useTranslation,
} from "@/shared/i18n"
import { Button, ButtonLink, Chip, IconLabel, PageBody, PageHeader, toast } from "@/shared/ui"
import styles from "./employer-selection-page.module.css"

function draftOf(selection: Selection): NeedDraft {
  const need = selection.need
  return {
    kind: "draft",
    title: need.title,
    specialization: need.specialization,
    grade: need.grade,
    stack: need.stack,
    work_format: need.work_format,
    city: need.city,
    salary_from: need.salary_from,
    salary_to: need.salary_to,
    confidence: {},
    uncertain: [],
    salary_basis: "gross",
  }
}

function HeaderActions({ selection }: { readonly selection: Selection }) {
  const { t } = useTranslation("selection")
  const errorText = useErrorText()
  const navigate = useNavigate()
  const build = useBuildSelection()
  const needId = selection.need_id
  if (needId === null)
    return (
      <Button
        icon="edit"
        onClick={() => navigate("/employer/needs/new", { state: { draft: draftOf(selection) } })}
      >
        {t("fixDraft")}
      </Button>
    )
  return (
    <>
      <ButtonLink to={`/employer/needs/${needId}`} variant="secondary" icon="need">
        {t("need")}
      </ButtonLink>
      <VacancyTestAction needId={needId} />
      <Button
        icon="refresh"
        pending={build.isPending}
        pendingLabel={t("rebuilding")}
        onClick={() =>
          build.mutate(needId, {
            onSuccess: (next) => navigate(`/employer/selections/${next.id}`, { replace: true }),
            onError: (error) => toast.error(errorText(error)),
          })
        }
      >
        {t("rebuild")}
      </Button>
    </>
  )
}

export function EmployerSelectionPage() {
  const { t } = useTranslation(["selection", "need"])
  const { id = "" } = useParams()
  const names = useCatalogNames()
  const format = useFormatters()
  const query = useSelection(id)
  const selection = query.data?.pages[0]
  useDocumentTitle(selection?.title ?? t("title"))

  return (
    <>
      <PageHeader
        title={selection?.title ?? t("title")}
        crumbs={[{ label: t("need:list.title"), to: "/employer/needs" }]}
        meta={
          selection === undefined ? undefined : (
            <span className={styles.meta}>
              <Chip icon={specializationIcon(selection.specialization.code)} tone="accent">
                {names.specialization(selection.specialization)}
              </Chip>
              <Chip icon={gradeIcon(selection.grade.code)} tone="accent">
                {names.grade(selection.grade)}
              </Chip>
              <IconLabel icon="clock" tone="secondary" className={styles.built}>
                {t("built", { date: format.dateTimeMoscow(selection.created_at) })}
              </IconLabel>
              {selection.need_id === null ? (
                <IconLabel icon="info" tone="accent" className={styles.built}>
                  {t("draftNote")}
                </IconLabel>
              ) : null}
            </span>
          )
        }
        actions={selection === undefined ? undefined : <HeaderActions selection={selection} />}
      />
      <PageBody>
        <SelectionBoard
          key={id}
          selectionId={id}
          invite={(entry, current) => (
            <InviteAction
              candidateId={entry.candidate_id}
              selectionId={current.id}
              needId={current.need_id}
              label={anonymousId(entry.candidate_id)}
              defaults={{
                description: current.need.title,
                salaryFrom: current.need.salary_from,
                salaryTo: current.need.salary_to,
              }}
            />
          )}
        />
      </PageBody>
    </>
  )
}
