import { Link } from "react-router"
import { useApplications } from "@/entities/application"
import { isOpenStatus, useSentInvitations } from "@/entities/invitation"
import { useNeeds } from "@/entities/need"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { type IconName, Skeleton, Stat } from "@/shared/ui"
import { candidateCount, latestByNeed, useRecentSelections } from "../recent-selections"
import styles from "./overview-stats.module.css"

type Figure = number | null | undefined

interface Tile {
  readonly key: string
  readonly icon: IconName
  readonly value: Figure
  readonly to: string
  readonly urgent?: boolean
}

interface Loadable<T> {
  readonly data: T | undefined
  readonly isError: boolean
}

function figure<T>(query: Loadable<T>, count: (data: T) => number): Figure {
  if (query.data !== undefined) return count(query.data)
  return query.isError ? null : undefined
}

function useTiles(): readonly Tile[] {
  const needs = useNeeds()
  const selections = useRecentSelections()
  const sent = useSentInvitations()
  const applications = useApplications()
  const candidates =
    needs.data !== undefined && selections.data !== undefined
      ? { data: { needs: needs.data, latest: latestByNeed(selections.data) }, isError: false }
      : { data: undefined, isError: needs.isError || selections.isError }
  return [
    {
      key: "needs",
      icon: "need",
      value: figure(needs, (data) => data.length),
      to: "/employer/needs",
    },
    {
      key: "candidates",
      icon: "candidates",
      to: "/employer/needs",
      value: figure(candidates, ({ needs: list, latest }) =>
        list.reduce((sum, need) => {
          const selection = latest.get(need.id)
          return selection === undefined ? sum : sum + candidateCount(selection)
        }, 0),
      ),
    },
    {
      key: "decide",
      icon: "application",
      to: "/employer/invitations?tab=applications",
      urgent: true,
      value: figure(
        applications,
        (data) =>
          data.filter((item) => isOpenStatus(item.status) && item.revoked_at === null).length,
      ),
    },
    {
      key: "waiting",
      icon: "invitation",
      to: "/employer/invitations",
      value: figure(
        sent,
        (data) =>
          data.invitations.filter((item) => isOpenStatus(item.status) && item.revoked_at === null)
            .length,
      ),
    },
  ]
}

export function OverviewStats() {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const tiles = useTiles()
  return (
    <ul className={styles.stats} aria-label={t("overview.stats.label")}>
      {tiles.map((tile, index) => (
        <li key={tile.key} className={styles.item} style={staggerStyle(index)}>
          <Link to={tile.to} className={styles.tile} viewTransition>
            {tile.value === undefined ? (
              <Skeleton lines={2} />
            ) : (
              <Stat
                label={t(`overview.stats.${tile.key}` as never)}
                icon={tile.icon}
                size="large"
                tone={tile.urgent === true && (tile.value ?? 0) > 0 ? "attention" : "default"}
                value={tile.value === null ? null : format.integer(tile.value)}
              />
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
}
