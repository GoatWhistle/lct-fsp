import type { VacancyTestExample } from "@/shared/api"
import { BackendText, useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { IconLabel, ScrollArea } from "@/shared/ui"
import styles from "./example-card.module.css"

export interface ExampleCardProps {
  readonly example: VacancyTestExample
  readonly index: number
}

export function ExampleCard({ example, index }: ExampleCardProps) {
  const { t } = useTranslation("test")
  const names = useCatalogNames()
  return (
    <article className={styles.example} style={staggerStyle(index)}>
      <IconLabel icon="topic" tone="secondary" className={styles.topic}>
        {names.topic(example.topic)}
      </IconLabel>
      <BackendText as="p" className={styles.prompt}>
        {example.prompt}
      </BackendText>
      {example.code === null ? null : (
        <ScrollArea label={t("code")} className={styles.code}>
          <pre className={styles.listing}>
            <code>{example.code}</code>
          </pre>
        </ScrollArea>
      )}
      {example.options.length === 0 ? null : (
        <ol className={styles.options}>
          {example.options.map((option) => (
            <li key={option.letter} className={styles.option}>
              <span className={styles.letter}>{option.letter}</span>
              <BackendText>{option.text}</BackendText>
            </li>
          ))}
        </ol>
      )}
    </article>
  )
}
