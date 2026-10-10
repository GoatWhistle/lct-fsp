import { type ReactNode, useState } from "react"
import { useFspStatus, useRefreshFsp, useUnlinkFsp } from "@/entities/profile"
import type { FspStatus } from "@/shared/api"
import { useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import {
  Button,
  ConfirmDialog,
  FlagRow,
  FspMark,
  LoadError,
  Menu,
  Skeleton,
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
  const note = !status.linked
    ? t("fsp.notLinkedNote")
    : status.fetched_at === null
      ? t("fsp.noSnapshot")
      : t("fsp.snapshot", { date: format.dateTime(status.fetched_at) })
  return (
    <FlagRow
      mark={<FspMark className={styles.mark} />}
      title={
        status.linked ? (
          <span className={styles.linked}>
            {t("fsp.linked")}
            {status.fsp_id === null ? null : <span className={styles.id}>{status.fsp_id}</span>}
          </span>
        ) : (
          t("fsp.notLinkedTitle")
        )
      }
      note={note}
      active={status.linked}
      trailing={status.linked ? <LinkedActions status={status} /> : linkAction}
      className={styles.status}
    />
  )
}

export interface FspSectionProps {
  readonly linkAction: ReactNode
}

export function FspSection({ linkAction }: FspSectionProps) {
  const { t } = useTranslation("profile")
  const fsp = useFspStatus()
  return (
    <EditorSection id="fsp" title={t("sections.fsp")}>
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
