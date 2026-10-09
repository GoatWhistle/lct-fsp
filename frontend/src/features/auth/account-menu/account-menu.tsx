import { useNavigate } from "react-router"
import type { User } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Menu, type MenuItem, type Placement } from "@/shared/ui"
import { useLogout } from "../logout/use-logout"

export interface AccountMenuProps {
  readonly user: User
  readonly placement?: Placement | undefined
  readonly iconOnly?: boolean | undefined
}

export function AccountMenu({ user, placement = "top-start", iconOnly = false }: AccountMenuProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const logout = useLogout()
  const profile: MenuItem =
    user.role === "employer"
      ? {
          id: "company",
          label: t("shell.company"),
          icon: "company",
          onSelect: () => navigate("/employer/company"),
        }
      : {
          id: "profile",
          label: t("nav.profile"),
          icon: "profile",
          onSelect: () => navigate("/candidate/profile"),
        }
  return (
    <Menu
      label={t("shell.account")}
      icon="profile"
      placement={placement}
      iconOnly={iconOnly}
      items={[
        profile,
        {
          id: "logout",
          label: t("action.logout"),
          icon: "logout",
          onSelect: () => logout.mutate(),
        },
      ]}
    />
  )
}
