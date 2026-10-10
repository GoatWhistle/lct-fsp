import { useNavigate } from "react-router"
import { COMPANY_DIALOG_LINK } from "@/entities/company"
import { PROFILE_DIALOG_LINK } from "@/entities/profile"
import type { User } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Menu, type MenuItem, type Placement } from "@/shared/ui"
import { useLogout } from "../logout/use-logout"
import { useAccountName } from "./use-account-name"

export interface AccountMenuProps {
  readonly user: User
  readonly placement?: Placement | undefined
  readonly iconOnly?: boolean | undefined
  readonly className?: string | undefined
}

export function AccountMenu({
  user,
  placement = "top-start",
  iconOnly = false,
  className,
}: AccountMenuProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const logout = useLogout()
  const name = useAccountName(user)
  const profile: MenuItem =
    user.role === "employer"
      ? {
          id: "company",
          label: t("shell.company"),
          icon: "company",
          onSelect: () => navigate(COMPANY_DIALOG_LINK),
        }
      : {
          id: "profile",
          label: t("nav.profile"),
          icon: "profile",
          onSelect: () => navigate(PROFILE_DIALOG_LINK),
        }
  return (
    <Menu
      label={iconOnly ? t("shell.account") : name}
      icon={user.role === "employer" ? "company" : "profile"}
      placement={placement}
      iconOnly={iconOnly}
      className={className}
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
