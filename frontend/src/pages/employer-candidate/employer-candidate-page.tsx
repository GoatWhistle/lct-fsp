import { useParams } from "react-router"
import { useCandidateCard } from "@/entities/selection"
import { CandidateCardView } from "@/features/candidate-card"
import { InviteAction } from "@/features/invite"
import { anonymousId } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { LoadError, PageBody, PageHeader, Skeleton } from "@/shared/ui"

const NO_DEFAULTS = { description: "", salaryFrom: null, salaryTo: null }

export function EmployerCandidatePage() {
  const { t } = useTranslation("card")
  const { id = "" } = useParams()
  const card = useCandidateCard(id)
  const label = anonymousId(id)
  const title = card.data?.disclosed?.full_name ?? t("title", { id: label })
  useDocumentTitle(title)
  return (
    <>
      <PageHeader title={title} crumbs={[{ label: t("back"), to: "/employer/candidates" }]} />
      <PageBody>
        {card.isError ? (
          <LoadError
            error={card.error}
            onRetry={() => void card.refetch()}
            pending={card.isFetching}
          />
        ) : card.data === undefined ? (
          <Skeleton shape="block" />
        ) : (
          <CandidateCardView
            card={card.data}
            invite={
              <InviteAction candidateId={id} label={label} defaults={NO_DEFAULTS} size="regular" />
            }
          />
        )}
      </PageBody>
    </>
  )
}
