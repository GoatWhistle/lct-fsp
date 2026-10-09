import { useNavigate, useParams, useSearchParams } from "react-router"
import { useApplications } from "@/entities/application"
import { isOpenStatus, useSentInvitations } from "@/entities/invitation"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader, Tabs } from "@/shared/ui"
import { ApplicationsTab } from "./applications-tab/applications-tab"
import { InvitationsTab } from "./invitations-tab/invitations-tab"

type Tab = "invitations" | "applications"

export function EmployerInvitationsPage() {
  const { t } = useTranslation("employer")
  const { id } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const sent = useSentInvitations()
  const applications = useApplications()
  const tab: Tab =
    id === undefined && params.get("tab") === "applications" ? "applications" : "invitations"
  useDocumentTitle(t("invitations.title"))
  const unread = sent.data?.invitations.filter((item) => item.unread_messages > 0).length
  const waiting = applications.data?.filter((item) => isOpenStatus(item.status)).length
  const change = (next: Tab) =>
    navigate(
      next === "applications" ? "/employer/invitations?tab=applications" : "/employer/invitations",
    )
  return (
    <>
      <PageHeader title={t("invitations.title")} description={t("invitations.lead")} />
      <PageBody>
        <Tabs<Tab>
          label={t("invitations.title")}
          value={tab}
          onChange={change}
          tabs={[
            {
              value: "invitations",
              label: t("invitations.tab"),
              icon: "invitation",
              count: unread === 0 ? undefined : unread,
            },
            {
              value: "applications",
              label: t("invitations.applicationsTab"),
              icon: "application",
              count: waiting === 0 ? undefined : waiting,
            },
          ]}
        >
          {tab === "invitations" ? <InvitationsTab selectedId={id ?? null} /> : <ApplicationsTab />}
        </Tabs>
      </PageBody>
    </>
  )
}
