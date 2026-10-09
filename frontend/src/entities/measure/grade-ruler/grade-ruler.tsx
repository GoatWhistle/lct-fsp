import { clsx } from "clsx"
import type { CSSProperties } from "react"
import type { Level } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { GRADE_ORDER, GRADE_THRESHOLD, gradeAt, scalePercent } from "../grade-scale"
import { useLevelWords } from "../use-level-words"
import styles from "./grade-ruler.module.css"

export type GradeRulerSize = "full" | "inline"

export interface RulerMarker {
  readonly theta: number
  readonly label: string
}

export interface GradeRulerProps {
  readonly level: Level
  readonly size?: GradeRulerSize
  readonly animate?: boolean
  readonly required?: number | null | undefined
  readonly secondary?: RulerMarker | null | undefined
  readonly caption?: boolean
  readonly className?: string | undefined
}

const ZONES = ["below", ...GRADE_ORDER] as const

function railStyle(percent: number, from: number | null): CSSProperties {
  return {
    transform: `translateX(${percent}%)`,
    ...(from === null ? {} : { "--travel-from": `${from}%` }),
  } as CSSProperties
}

export function GradeRuler({
  level,
  size = "full",
  animate = false,
  required,
  secondary,
  caption = size === "full",
  className,
}: GradeRulerProps) {
  const { t } = useTranslation("measure")
  const names = useCatalogNames()
  const words = useLevelWords()
  const node = scalePercent(level.theta)
  const bandStart = scalePercent(level.theta - level.theta_sd)
  const bandWidth = scalePercent(level.theta + level.theta_sd) - bandStart
  const label =
    required === undefined || required === null
      ? words.describe(level)
      : `${words.describe(level)}. ${t("ruler.required")}: ${names.grade(gradeAt(required) ?? "intern")}`

  return (
    <figure
      className={clsx(styles.ruler, className)}
      data-size={size}
      data-animate={animate}
      data-motion={animate ? "fade" : undefined}
    >
      <div className={styles.track} role="img" aria-label={label}>
        <div className={styles.zones} aria-hidden="true">
          {ZONES.map((zone) => (
            <span key={zone} className={styles.zone} data-zone={zone} />
          ))}
        </div>
        <span className={styles.rail} style={railStyle(bandStart, null)} aria-hidden="true">
          <span
            className={styles.band}
            style={{ "--band-width": `${bandWidth}%` } as CSSProperties}
          />
        </span>
        {required === undefined || required === null ? null : (
          <span
            className={styles.rail}
            style={railStyle(scalePercent(required), null)}
            aria-hidden="true"
          >
            <span className={styles.required} />
          </span>
        )}
        {secondary === undefined || secondary === null ? null : (
          <span
            className={styles.rail}
            style={railStyle(scalePercent(secondary.theta), null)}
            aria-hidden="true"
          >
            <span className={styles.secondary} />
          </span>
        )}
        <span
          className={styles.rail}
          style={railStyle(node, animate ? 50 : null)}
          aria-hidden="true"
        >
          <span className={styles.node} />
        </span>
      </div>
      {size === "full" && (
        <div className={styles.scale} aria-hidden="true">
          {ZONES.map((zone) => (
            <span key={zone} className={styles.scaleLabel}>
              {zone === "below" ? t("ruler.below") : names.grade(zone)}
            </span>
          ))}
        </div>
      )}
      {caption && (
        <figcaption className={styles.caption}>
          <span className={styles.words}>{words.band(level.band)}</span>
          <span className={styles.uncertainty}>{words.uncertainty(level.theta_sd)}</span>
          {secondary === undefined || secondary === null ? null : (
            <span className={styles.secondaryLabel}>{secondary.label}</span>
          )}
        </figcaption>
      )}
    </figure>
  )
}

export function thresholdOf(grade: string): number | null {
  return grade in GRADE_THRESHOLD ? GRADE_THRESHOLD[grade as keyof typeof GRADE_THRESHOLD] : null
}
