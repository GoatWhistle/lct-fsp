import { type ReactNode, useState } from "react"
import { useFspStatus, useRefreshFsp, useUnlinkFsp } from "@/entities/profile"
import type { FspStatus } from "@/shared/api"
import { useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import {
  Button,
  ConfirmDialog,
  IconLabel,
  LoadError,
  Menu,
  Skeleton,
  StatusBadge,
  toast,
} from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import { Achievements, Divergences } from "./fsp-achievements"
import styles from "./fsp-section.module.css"

function LinkedActions({ status }: { readonly status: FspStatus }) {
  const { t } = useTranslation("profile")
  const errorText = useErrorText()
  const refresh = useRefreshFsp()
  const unlink = useUnlinkFsp()
  const [confirming, setConfirming] = useState(false)
  const onError = (error: unknown) => toast.error(errorText(error))
  return (
    <div className={styles.actions}>
      <Button
        variant="secondary"
        size="compact"
        icon="refresh"
        pending={refresh.isPending}
        onClick={() =>
          refresh.mutate(undefined, { onSuccess: () => toast.success(t("fsp.refreshed")), onError })
        }
      >
        {t("fsp.refresh")}
      </Button>
      {status.can_unlink ? (
        <Menu
          items={[
            {
              id: "unlink",
              label: t("fsp.unlink"),
              icon: "unlink",
              onSelect: () => setConfirming(true),
            },
          ]}
        />
      ) : null}
      <ConfirmDialog
        open={confirming}
        tone="danger"
        title={t("fsp.unlinkTitle")}
        description={t("fsp.unlinkText")}
        confirmLabel={t("fsp.unlink")}
        pending={unlink.isPending}
        onConfirm={() =>
          unlink.mutate(undefined, { onSuccess: () => setConfirming(false), onError })
        }
        onClose={() => setConfirming(false)}
      />
    </div>
  )
}

interface StatusLineProps {
  readonly status: FspStatus
  readonly linkAction: ReactNode
}

function StatusLine({ status, linkAction }: StatusLineProps) {
  const { t } = useTranslation("profile")
  const format = useFormatters()
  if (!status.linked)
    return (
      <div className={styles.status}>
        <p className={styles.note}>{t("fsp.notLinked")}</p>
        {linkAction}
      </div>
    )
  return (
    <div className={styles.status}>
      <div className={styles.linked}>
        <StatusBadge tone="positive" icon="fsp">
          {t("fsp.linked")}
        </StatusBadge>
        {status.fsp_id === null ? null : <span className={styles.id}>{status.fsp_id}</span>}
        <IconLabel icon="calendar" tone="secondary">
          {status.fetched_at === null
            ? t("fsp.noSnapshot")
            : t("fsp.snapshot", { date: format.dateTime(status.fetched_at) })}
        </IconLabel>
      </div>
      <LinkedActions status={status} />
    </div>
  )
}

export interface FspSectionProps {
  readonly linkAction: ReactNode
}

export function FspSection({ linkAction }: FspSectionProps) {
  const { t } = useTranslation("profile")
  const fsp = useFspStatus()
  return (
    <EditorSection id="fsp" title={t("sections.fsp")} description={t("fsp.lead")}>
      {fsp.isError ? (
        <LoadError error={fsp.error} onRetry={() => void fsp.refetch()} pending={fsp.isFetching} />
      ) : fsp.data === undefined ? (
        <Skeleton lines={3} />
      ) : (
        <>
          <StatusLine status={fsp.data} linkAction={linkAction} />
          {fsp.data.linked && fsp.data.achievements.length === 0 ? (
            <p className={styles.note}>{t("fsp.noAchievements")}</p>
          ) : null}
          {fsp.data.achievements.length === 0 ? null : (
            <Achievements items={fsp.data.achievements} />
          )}
          {fsp.data.divergences.length === 0 ? null : <Divergences items={fsp.data.divergences} />}
        </>
      )}
    </EditorSection>
  )
}
