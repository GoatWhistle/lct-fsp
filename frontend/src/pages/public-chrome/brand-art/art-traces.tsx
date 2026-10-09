import type { CSSProperties } from "react"
import styles from "./art-traces.module.css"
import { readout, readoutAnchor, TRACES } from "./traces"

const READOUT_LIFT = 14

export function ArtTraces() {
  return (
    <svg className={styles.traces} viewBox="0 0 480 480" aria-hidden="true">
      {TRACES.map((trace, index) => (
        <g
          key={trace.d}
          className={styles.group}
          data-trace=""
          style={{ "--i": index } as CSSProperties}
        >
          <path className={styles.trace} d={trace.d} pathLength={1} />
          <path className={styles.lit} d={trace.d} pathLength={1} />
          <path className={styles.signal} d={trace.d} pathLength={1} />
          <circle className={styles.node} cx={trace.from[0]} cy={trace.from[1]} r={5} />
          {trace.accent === true && (
            <circle className={styles.ping} cx={trace.to[0]} cy={trace.to[1]} r={6} />
          )}
          <circle className={styles.halo} cx={trace.to[0]} cy={trace.to[1]} r={12} />
          <circle
            className={styles.node}
            data-accent={trace.accent === true}
            cx={trace.to[0]}
            cy={trace.to[1]}
            r={6}
          />
          <text
            className={styles.readout}
            x={trace.from[0]}
            y={trace.from[1] - READOUT_LIFT}
            textAnchor={readoutAnchor(trace)}
          >
            {readout(trace)}
          </text>
        </g>
      ))}
    </svg>
  )
}
