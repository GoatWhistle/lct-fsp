import styles from "./event-pulse.module.css"
import { arcPath, CITIES, type EventCityId, HUB } from "./network"

const RINGS = [0, 1, 2] as const

export interface EventPulseProps {
  readonly city: EventCityId
}

export function EventPulse({ city }: EventPulseProps) {
  const d = arcPath({ from: city, to: HUB })
  const [cx, cy] = CITIES[city]
  return (
    <g className={styles.pulse}>
      <path className={styles.glow} d={d} pathLength={1} />
      <path className={styles.line} d={d} pathLength={1} />
      <path className={styles.comet} d={d} pathLength={1} />
      {RINGS.map((ring) => (
        <circle key={ring} className={styles.ring} data-ring={ring} cx={cx} cy={cy} r={3} />
      ))}
    </g>
  )
}
