import { clsx } from "clsx"
import { type HTMLAttributes, type ReactNode, useId } from "react"
import { staggerStyle } from "../../../motion"
import styles from "./card.module.css"

export type CardLevel = "top" | "inner" | "section"
export type CardTone = "default" | "inverse"

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  readonly level?: CardLevel
  readonly tone?: CardTone
  readonly as?: "section" | "article" | "aside" | "div"
  readonly motionIndex?: number | undefined
  readonly title?: ReactNode
  readonly description?: ReactNode
  readonly actions?: ReactNode
  readonly titleId?: string | undefined
  readonly children: ReactNode
}

interface CardHeaderProps {
  readonly level: CardLevel
  readonly titleId: string
  readonly title: ReactNode
  readonly description: ReactNode
  readonly actions: ReactNode
}

function CardHeader({ level, titleId, title, description, actions }: CardHeaderProps) {
  const Heading = level === "top" ? "h2" : "h3"
  return (
    <header className={styles.header}>
      <hgroup className={styles.heading}>
        <Heading id={titleId} className={styles.title}>
          {title}
        </Heading>
        {description !== undefined && <p className={styles.description}>{description}</p>}
      </hgroup>
      {actions !== undefined && <div className={styles.actions}>{actions}</div>}
    </header>
  )
}

export function Card({
  level = "top",
  tone = "default",
  as: Tag = "section",
  motionIndex,
  title,
  description,
  actions,
  titleId,
  className,
  style,
  children,
  ...rest
}: CardProps) {
  const generatedId = useId()
  const headingId = titleId ?? generatedId
  const titled = title !== undefined
  const entering = motionIndex !== undefined
  const labelled = titled && rest["aria-label"] === undefined
  return (
    <Tag
      aria-labelledby={labelled ? headingId : undefined}
      {...rest}
      className={clsx(
        styles.card,
        titled && styles.titled,
        level === "inner" && styles.inner,
        level === "section" && styles.section,
        tone === "inverse" && styles.inverse,
        entering && styles.entering,
        className,
      )}
      style={entering ? { ...style, ...staggerStyle(motionIndex) } : style}
      data-level={level}
      data-surface={tone === "inverse" ? "inverse" : undefined}
      data-motion={entering ? "fade" : undefined}
    >
      {titled && (
        <CardHeader
          level={level}
          titleId={headingId}
          title={title}
          description={description}
          actions={actions}
        />
      )}
      {children}
    </Tag>
  )
}
