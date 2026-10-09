export const MAP_SIZE = { width: 471, height: 312 } as const

export const MAP_VIEWBOX = `0 0 ${MAP_SIZE.width} ${MAP_SIZE.height}`

export type CityId =
  | "kaliningrad"
  | "petersburg"
  | "moscow"
  | "krasnodar"
  | "kazan"
  | "yekaterinburg"
  | "novosibirsk"
  | "krasnoyarsk"
  | "irkutsk"
  | "yakutsk"
  | "khabarovsk"
  | "vladivostok"

export const CITIES: Readonly<Record<CityId, readonly [number, number]>> = {
  kaliningrad: [38, 94],
  petersburg: [79, 109],
  moscow: [73, 141],
  krasnodar: [29, 183],
  kazan: [100, 170],
  yekaterinburg: [134, 189],
  novosibirsk: [198, 229],
  krasnoyarsk: [233, 230],
  irkutsk: [272, 253],
  yakutsk: [341, 182],
  khabarovsk: [390, 243],
  vladivostok: [392, 277],
}

export const HUB: CityId = "moscow"

export const EVENT_CITIES = [
  "novosibirsk",
  "kazan",
  "vladivostok",
  "petersburg",
  "yekaterinburg",
  "krasnoyarsk",
  "yakutsk",
] as const satisfies readonly CityId[]

export type EventCityId = (typeof EVENT_CITIES)[number]

export interface Link {
  readonly from: CityId
  readonly to: CityId
  readonly long?: boolean
}

export const LINKS: readonly Link[] = [
  { from: "petersburg", to: "moscow" },
  { from: "kaliningrad", to: "moscow" },
  { from: "krasnodar", to: "moscow" },
  { from: "kazan", to: "moscow" },
  { from: "yekaterinburg", to: "kazan" },
  { from: "novosibirsk", to: "yekaterinburg" },
  { from: "krasnoyarsk", to: "novosibirsk" },
  { from: "irkutsk", to: "krasnoyarsk" },
  { from: "yakutsk", to: "irkutsk" },
  { from: "vladivostok", to: "khabarovsk" },
  { from: "khabarovsk", to: "yakutsk" },
  { from: "novosibirsk", to: "moscow", long: true },
  { from: "vladivostok", to: "moscow", long: true },
]

const LIFT = 0.22

export function arcPath(link: Link): string {
  const [x1, y1] = CITIES[link.from]
  const [x2, y2] = CITIES[link.to]
  const distance = Math.hypot(x2 - x1, y2 - y1)
  const cx = (x1 + x2) / 2
  const cy = (y1 + y2) / 2 - distance * LIFT
  return `M${x1} ${y1}Q${cx.toFixed(1)} ${cy.toFixed(1)} ${x2} ${y2}`
}

const GOLDEN = 0.618034
const SHORT_LINK = 90
const LONG_LINK = 200

export type Tempo = "fast" | "base" | "slow"

export function linkTempo(link: Link): Tempo {
  const [x1, y1] = CITIES[link.from]
  const [x2, y2] = CITIES[link.to]
  const length = Math.hypot(x2 - x1, y2 - y1)
  if (length < SHORT_LINK) return "fast"
  return length > LONG_LINK ? "slow" : "base"
}

export function phase(index: number): number {
  return (index * GOLDEN) % 1
}

export function cityTempo(index: number): Tempo {
  const tempos: readonly Tempo[] = ["base", "slow", "fast"]
  return tempos[index % tempos.length] ?? "base"
}
