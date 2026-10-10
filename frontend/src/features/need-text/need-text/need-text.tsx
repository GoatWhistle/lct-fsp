import { useState } from "react"
import { useNavigate } from "react-router"
import { useParseNeed } from "@/entities/need"
import { useCatalogNames, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Button, Card, Form, TextArea, Trace } from "@/shared/ui"
import { draftWithSpecialization } from "../draft-input"
import { DraftPlaceholder } from "../draft-result/draft-placeholder"
import { DraftResult } from "../draft-result/draft-result"
import { PARSE_STAGES, useParseStatuses } from "../parse-stage/parse-stage"
import styles from "./need-text.module.css"

const MAX_LENGTH = 20000

export function NeedText() {
  const { t } = useTranslation("need")
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const parse = useParseNeed()
  const [text, setText] = useState("")
  const statuses = useParseStatuses(parse.isPending, parse.isSuccess)
  const result = parse.data

  return (
    <div className={styles.layout}>
      <Card title={t("text.field")} className={styles.input}>
        <Form onSubmit={() => text.trim() !== "" && parse.mutate(text)} className={styles.form}>
          <TextArea
            label={t("text.field")}
            hideLabel
            value={text}
            onChange={setText}
            placeholder={t("text.placeholder")}
            maxLength={MAX_LENGTH}
            minRows={10}
            className={styles.area}
            hint={t("text.counter", {
              length: format.integer(text.length),
              max: format.integer(MAX_LENGTH),
            })}
          />
          <div className={styles.actions}>
            <Button
              type="submit"
              icon="llm"
              pending={parse.isPending}
              disabled={text.trim() === ""}
            >
              {t("text.parse")}
            </Button>
            <Button variant="ghost" icon="file" onClick={() => setText(t("text.placeholder"))}>
              {t("text.example")}
            </Button>
          </div>
          <Trace
            label={t("text.parse")}
            orientation="horizontal"
            animate
            steps={PARSE_STAGES.map((key, index) => ({
              key,
              title: t(`need:text.${key}` as never),
              status: statuses[index] ?? "upcoming",
            }))}
          />
        </Form>
      </Card>
      <Swap swapKey={result === undefined ? "empty" : result.kind} as="div" className={styles.side}>
        {parse.isError ? <Banner tone="critical" title={errorText(parse.error)} /> : null}
        {result === undefined ? (
          <DraftPlaceholder pending={parse.isPending} className={styles.placeholder} />
        ) : result.kind === "draft" ? (
          <DraftResult draft={result} />
        ) : (
          <Card title={t("text.outTitle")} description={t("text.outText", { asked: result.asked })}>
            <div className={styles.actions}>
              {result.nearest.map((item) => (
                <Button
                  key={item.code}
                  variant="secondary"
                  icon="arrow-right"
                  iconPosition="end"
                  onClick={() =>
                    navigate("/employer/needs/new", {
                      state: { draft: draftWithSpecialization(item) },
                      viewTransition: true,
                    })
                  }
                >
                  {names.specialization(item)}
                </Button>
              ))}
            </div>
          </Card>
        )}
      </Swap>
    </div>
  )
}
