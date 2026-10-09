import { clsx } from "clsx"
import type { CSSProperties } from "react"
import styles from "./brand-art.module.css"

interface TracePath {
  readonly d: string
  readonly from: readonly [number, number]
  readonly to: readonly [number, number]
  readonly accent?: boolean
}

const TRACES: readonly TracePath[] = [
  { d: "M24 132H112a28 28 0 0 1 28 28v58", from: [24, 132], to: [140, 218], accent: true },
  { d: "M456 300H392a28 28 0 0 0-28 28v104", from: [456, 300], to: [364, 432] },
  { d: "M56 452v-48a28 28 0 0 1 28-28h64", from: [56, 452], to: [148, 376] },
  { d: "M428 28v64a28 28 0 0 1-28 28h-64", from: [428, 28], to: [336, 120], accent: true },
  { d: "M24 300h40", from: [24, 300], to: [64, 300] },
]

export interface BrandArtProps {
  readonly className?: string | undefined
}

export function BrandArt({ className }: BrandArtProps) {
  return (
    <figure className={clsx(styles.art, className)} aria-hidden="true">
      <img className={styles.face} src="/brand/face.webp" alt="" width={332} height={313} />
      <svg className={styles.traces} viewBox="0 0 480 480" aria-hidden="true">
        {TRACES.map((trace, index) => (
          <g key={trace.d} style={{ "--i": index } as CSSProperties}>
            <path className={styles.trace} d={trace.d} pathLength={1} />
            <circle className={styles.node} cx={trace.from[0]} cy={trace.from[1]} r={5} />
            <circle
              className={styles.node}
              data-accent={trace.accent === true}
              cx={trace.to[0]}
              cy={trace.to[1]}
              r={6}
            />
          </g>
        ))}
      </svg>
    </figure>
  )
}
