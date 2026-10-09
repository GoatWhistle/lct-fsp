import { useErrorText, useTranslation } from "@/shared/i18n"
import { FspMark, Icon, PlainButton, Spinner, toast } from "@/shared/ui"
import styles from "./fsp-tile.module.css"
import { type FspIntent, useFspAuthorize } from "./use-fsp-authorize"

export interface FspTileProps {
  readonly hint: string
  readonly intent?: FspIntent
}

export function FspTile({ hint, intent = "login" }: FspTileProps) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const authorize = useFspAuthorize()
  const title = t("brand.signInFsp")
  return (
    <PlainButton
      className={styles.tile}
      aria-busy={authorize.isPending}
      disabled={authorize.isPending}
      onClick={() =>
        authorize.mutate(intent, { onError: (error) => toast.error(errorText(error)) })
      }
    >
      <span className={styles.badge} data-surface="inverse">
        <FspMark className={styles.mark} />
      </span>
      <span className={styles.text}>
        <span className={styles.title}>{title}</span>
        <span className={styles.hint}>{hint}</span>
      </span>
      <span className={styles.end}>
        {authorize.isPending ? (
          <Spinner label={title} size="sm" />
        ) : (
          <Icon name="arrow-right" className={styles.arrow} />
        )}
      </span>
    </PlainButton>
  )
}
