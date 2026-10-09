export interface TracePath {
  readonly d: string
  readonly from: readonly [number, number]
  readonly to: readonly [number, number]
  readonly accent?: boolean
  readonly level: number
  readonly error: number
}

export const TRACES: readonly TracePath[] = [
  {
    d: "M12 128H104a28 28 0 0 1 28 28v62",
    from: [12, 128],
    to: [132, 218],
    accent: true,
    level: 1.42,
    error: 0.18,
  },
  {
    d: "M468 292H400a28 28 0 0 0-28 28v112",
    from: [468, 292],
    to: [372, 432],
    level: 0.87,
    error: 0.24,
  },
  {
    d: "M44 464v-56a28 28 0 0 1 28-28h80",
    from: [44, 464],
    to: [152, 380],
    level: 0.35,
    error: 0.31,
  },
  {
    d: "M436 16v68a28 28 0 0 1-28 28h-76",
    from: [436, 16],
    to: [332, 112],
    accent: true,
    level: 1.91,
    error: 0.12,
  },
  { d: "M12 300h56", from: [12, 300], to: [68, 300], level: 0.64, error: 0.27 },
  {
    d: "M468 196h-36a20 20 0 0 0-20 20v8",
    from: [468, 196],
    to: [412, 224],
    accent: true,
    level: 1.18,
    error: 0.15,
  },
  { d: "M232 476v-28", from: [232, 476], to: [232, 448], level: 0.52, error: 0.22 },
]

const CENTER = 240

export function readoutAnchor(trace: TracePath): "start" | "end" {
  return trace.from[0] < CENTER ? "start" : "end"
}

export function readout(trace: TracePath): string {
  return `${trace.level.toFixed(2)} ± ${trace.error.toFixed(2)}`
}
