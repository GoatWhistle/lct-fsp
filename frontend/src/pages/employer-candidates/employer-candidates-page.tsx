import { CandidateSearch } from "@/features/candidate-search"
import { InviteAction } from "@/features/invite"
import { anonymousId } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { ButtonLink, PageBody, PageHeader } from "@/shared/ui"

const NO_DEFAULTS = { description: "", salaryFrom: null, salaryTo: null }

export function EmployerCandidatesPage() {
  const { t } = useTranslation("search")
  useDocumentTitle(t("title"))
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("lead")}
        actions={
          <ButtonLink to="/employer/needs/new" variant="secondary" icon="match">
            {t("results.toNeed")}
          </ButtonLink>
        }
      />
      <PageBody>
        <CandidateSearch
          invite={(hit) => (
            <InviteAction
              candidateId={hit.candidate_id}
              label={anonymousId(hit.candidate_id)}
              defaults={NO_DEFAULTS}
            />
          )}
        />
      </PageBody>
    </>
  )
}
