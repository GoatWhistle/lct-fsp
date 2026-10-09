import styles from "./art-rings.module.css"

const CENTER = 240
const ORBIT = 212
const TICK_OUTER = 186
const TICK_INNER = 180
const TICK_MAJOR = 172
const TICK_STEP = 5
const MAJOR_EVERY = 30

function tick(angle: number): string {
  const radians = (angle * Math.PI) / 180
  const inner = angle % MAJOR_EVERY === 0 ? TICK_MAJOR : TICK_INNER
  const point = (radius: number) =>
    `${(CENTER + radius * Math.cos(radians)).toFixed(1)} ${(CENTER + radius * Math.sin(radians)).toFixed(1)}`
  return `M${point(inner)}L${point(TICK_OUTER)}`
}

const TICK_PATH = Array.from({ length: 360 / TICK_STEP }, (_, index) =>
  tick(index * TICK_STEP),
).join("")

export function ArtRings() {
  return (
    <svg className={styles.rings} viewBox="0 0 480 480" aria-hidden="true">
      <g className={styles.outer}>
        <circle className={styles.orbit} cx={CENTER} cy={CENTER} r={ORBIT} />
        <circle className={styles.rider} cx={CENTER + ORBIT} cy={CENTER} r={4} />
        <circle className={styles.riderRed} cx={CENTER - ORBIT} cy={CENTER} r={3} />
      </g>
      <g className={styles.inner}>
        <path className={styles.ticks} d={TICK_PATH} />
      </g>
    </svg>
  )
}
