import type { CandidatePath, TestItem } from "@/shared/api"
import { useStoredFlag } from "@/shared/hooks"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, LoadError, Skeleton, SplitPane } from "@/shared/ui"
import { AnswerPanel } from "../answer-panel/answer-panel"
import { ConditionPanel } from "../condition-panel/condition-panel"
import { useAnswer, useTestItem } from "../test.queries"
import { TestBar } from "../test-bar/test-bar"
import { useFocusCounters } from "../use-focus-counters"
import { VerificationTimer } from "../verification-timer/verification-timer"
import styles from "./test-screen.module.css"

const INTRO_KEY = "calibr-test-intro"

export interface TestScreenProps {
  readonly path: CandidatePath
  readonly exitTo: string
  readonly onFinished: (path: CandidatePath) => void
}

function Intro() {
  const { t } = useTranslation("test")
  const [open, setOpen] = useStoredFlag(INTRO_KEY, true)
  return (
    <Banner
      tone="info"
      icon="info"
      title={t("intro.adaptive")}
      open={open}
      className={styles.intro}
      action={
        <Button variant="secondary" size="compact" onClick={() => setOpen(false)}>
          {t("intro.hide")}
        </Button>
      }
    >
      {t("intro.noFeedback")}
    </Banner>
  )
}

function Workspace({
  item,
  onFinished,
}: {
  item: TestItem
  onFinished: TestScreenProps["onFinished"]
}) {
  const { t } = useTranslation("test")
  const answer = useAnswer(onFinished)
  const takeCounters = useFocusCounters(item.focus_consent, item.id)
  return (
    <Swap swapKey={item.id} as="div" className={styles.swap}>
      <SplitPane
        label={t("condition")}
        className={styles.split}
        start={<ConditionPanel item={item} />}
        end={
          <div className={styles.end}>
            {item.verification && item.deadline ? (
              <VerificationTimer deadline={item.deadline} onFinished={onFinished} />
            ) : (
              <Intro />
            )}
            <AnswerPanel
              key={item.id}
              item={item}
              pending={answer.isPending}
              error={answer.error}
              onSubmit={(response) => answer.mutate({ id: item.id, response, ...takeCounters() })}
            />
          </div>
        }
      />
    </Swap>
  )
}

export function TestScreen({ path, exitTo, onFinished }: TestScreenProps) {
  const { t } = useTranslation("test")
  const names = useCatalogNames()
  const item = useTestItem()
  const block = path.topic_block !== null || !!path.verification?.progress
  const title = path.verification?.progress
    ? t("protection.title")
    : path.topic_block !== null
      ? `${t("titleBlock")}: ${names.topic(path.topic_block.topic)}`
      : t(path.attempt?.express ? "titleExpress" : "title", {
          grade: names.grade(path.attempt?.grade ?? ""),
        })
  const number =
    item.data?.number ?? (path.attempt?.answered ?? path.topic_block?.answered ?? 0) + 1
  const max = item.data?.max_items ?? path.attempt?.max_items ?? path.topic_block?.items ?? 1

  return (
    <div className={styles.screen}>
      <TestBar title={title} number={number} max={max} block={block} exitTo={exitTo} />
      <main id="main" className={styles.main}>
        {item.isError ? (
          <div className={styles.state}>
            <LoadError
              error={item.error}
              onRetry={() => void item.refetch()}
              pending={item.isFetching}
            />
          </div>
        ) : item.data === undefined ? (
          <div className={styles.state} aria-busy="true">
            <Skeleton shape="block" />
            <Skeleton lines={4} />
          </div>
        ) : (
          <Workspace item={item.data} onFinished={onFinished} />
        )}
      </main>
    </div>
  )
}
