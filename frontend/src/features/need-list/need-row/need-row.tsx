import { useState } from "react"
import { useNavigate } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useDeleteNeed } from "@/entities/need"
import { useBuildSelection, useSelections } from "@/entities/selection"
import type { Need } from "@/shared/api"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import {
  Button,
  ButtonLink,
  Chip,
  ConfirmDialog,
  IconLabel,
  Menu,
  Tooltip,
  toast,
} from "@/shared/ui"
import styles from "./need-row.module.css"

export interface NeedRowProps {
  readonly need: Need
  readonly index: number
}

export function NeedRow({ need, index }: NeedRowProps) {
  const { t } = useTranslation("need")
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const selections = useSelections(need.id)
  const build = useBuildSelection()
  const remove = useDeleteNeed()
  const [confirming, setConfirming] = useState(false)
  const latest = selections.data?.[0]

  const rebuild = () =>
    build.mutate(need.id, {
      onSuccess: (selection) => navigate(`/employer/selections/${selection.id}`),
      onError: (error) => toast.error(errorText(error)),
    })

  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.head}>
        <ButtonLink to={`/employer/needs/${need.id}`} variant="link" className={styles.title}>
          {need.title}
        </ButtonLink>
        <span className={styles.badges}>
          <Chip icon={specializationIcon(need.specialization.code)} tone="accent">
            {names.specialization(need.specialization)}
          </Chip>
          <Chip icon={gradeIcon(need.grade.code)} tone="accent">
            {names.grade(need.grade)}
          </Chip>
        </span>
      </div>
      <span className={styles.stack}>
        {need.stack.slice(0, 6).map((tech) => (
          <Chip key={tech.code}>{tech.name}</Chip>
        ))}
      </span>
      <div className={styles.selection}>
        {latest === undefined ? (
          <span className={styles.muted}>{t("list.noSelection")}</span>
        ) : (
          <>
            <IconLabel icon="calendar" tone="secondary" className={styles.date}>
              {t("list.lastSelection", { date: format.dateTime(latest.created_at) })}
            </IconLabel>
            <span className={styles.counts}>
              <span>
                <strong>{latest.exact_total}</strong> {t("list.exact")}
              </span>
              <span>
                <strong>{latest.nearby_total}</strong> {t("list.nearby")}
              </span>
            </span>
          </>
        )}
      </div>
      <div className={styles.actions}>
        {latest === undefined ? (
          <Button
            variant="secondary"
            size="compact"
            icon="refresh"
            pending={build.isPending}
            pendingLabel={t("list.building")}
            onClick={rebuild}
          >
            {t("list.build")}
          </Button>
        ) : (
          <>
            <ButtonLink to={`/employer/selections/${latest.id}`} icon="match" size="compact">
              {t("list.open")}
            </ButtonLink>
            <Tooltip content={t("list.rebuild")}>
              <Button
                variant="ghost"
                size="icon"
                icon="refresh"
                pending={build.isPending}
                aria-label={t("list.rebuild")}
                onClick={rebuild}
              >
                {null}
              </Button>
            </Tooltip>
          </>
        )}
        <Menu
          label={t("list.more")}
          icon="more"
          iconOnly
          items={[
            {
              id: "edit",
              label: t("list.edit"),
              icon: "edit",
              onSelect: () => navigate(`/employer/needs/${need.id}`),
            },
            {
              id: "delete",
              label: t("list.delete"),
              icon: "trash",
              onSelect: () => setConfirming(true),
            },
          ]}
        />
      </div>
      <ConfirmDialog
        open={confirming}
        tone="danger"
        title={t("list.deleteTitle", { title: need.title })}
        description={t("list.deleteText")}
        confirmLabel={t("list.delete")}
        pending={remove.isPending}
        onClose={() => setConfirming(false)}
        onConfirm={() =>
          remove.mutate(need.id, {
            onSuccess: () => {
              setConfirming(false)
              toast.success(t("list.deleted"))
            },
            onError: (error) => toast.error(errorText(error)),
          })
        }
      />
    </li>
  )
}
