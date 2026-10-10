import { PROFILE_FSP_LINK } from "@/entities/profile"
import type { FeedbackHint } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, Icon, type IconName } from "@/shared/ui"
import { BlockButton } from "../block-button/block-button"
import styles from "./feedback-panel.module.css"

const ACTION_ICON: Readonly<Record<FeedbackHint["action"]["kind"], IconName>> = {
  regular_task: "task",
  topic_block: "test",
  link_fsp: "fsp",
}

function HintAction({ hint }: { readonly hint: FeedbackHint }) {
  const { t } = useTranslation("overview")
  if (hint.action.kind === "link_fsp")
    return (
      <ButtonLink to={PROFILE_FSP_LINK} variant="secondary" size="compact" icon="fsp">
        {t("feedback.linkFsp")}
      </ButtonLink>
    )
  if (hint.action.kind === "regular_task")
    return (
      <ButtonLink to="/candidate/tasks" variant="secondary" size="compact" icon="task">
        {t("feedback.toTasks")}
      </ButtonLink>
    )
  return (
    <BlockButton
      topic={hint.topic?.code ?? ""}
      blockedUntil={hint.action.available ? null : hint.action.available_at}
    />
  )
}

export function HintRow({ hint, index }: { readonly hint: FeedbackHint; readonly index: number }) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const format = useFormatters()
  const topic = hint.topic === null ? "" : names.topic(hint.topic)
  const title =
    hint.action.kind === "link_fsp"
      ? t("feedback.fspTitle")
      : t(`feedback.scenario.${hint.scenario ?? "default"}`, { topic })
  return (
    <li className={styles.hint} style={staggerStyle(index)}>
      <Icon name={ACTION_ICON[hint.action.kind]} size="md" className={styles.hintIcon} />
      <div className={styles.hintBody}>
        <p className={styles.hintTitle}>{title}</p>
        {hint.action.kind === "link_fsp" ? (
          <p className={styles.hintText}>{t("feedback.fspText")}</p>
        ) : null}
        {hint.gain === null ? null : (
          <p className={styles.gain}>
            {hint.places === null || hint.places <= 0
              ? t("feedback.gain", { gain: format.percent(hint.gain) })
              : t("feedback.gainPlaces", {
                  gain: format.percent(hint.gain),
                  places: format.number(hint.places),
                })}
          </p>
        )}
      </div>
      <div className={styles.hintAction}>
        <HintAction hint={hint} />
      </div>
    </li>
  )
}
