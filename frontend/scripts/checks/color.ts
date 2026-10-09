export interface Rgba {
  readonly r: number
  readonly g: number
  readonly b: number
  readonly a: number
}

const HEX = /^#([0-9a-f]{6})$/i
const CHANNEL_MAX = 255
const HEX_RADIX = 16
const LINEAR_THRESHOLD = 0.04045
const LINEAR_SLOPE = 12.92
const GAMMA_OFFSET = 0.055
const GAMMA_SCALE = 1.055
const GAMMA = 2.4
const ENCODE_THRESHOLD = 0.0031308
const CUBE = 3
const PERCENT = 100

export function parseHex(value: string): Rgba | null {
  const match = HEX.exec(value.trim())
  if (match === null) return null
  const digits = match[1] ?? ""
  const [r, g, b] = [0, 2, 4].map((start) =>
    Number.parseInt(digits.slice(start, start + 2), HEX_RADIX),
  )
  return { r: r ?? 0, g: g ?? 0, b: b ?? 0, a: 1 }
}

function toLinear(channel: number): number {
  const value = channel / CHANNEL_MAX
  return value <= LINEAR_THRESHOLD
    ? value / LINEAR_SLOPE
    : ((value + GAMMA_OFFSET) / GAMMA_SCALE) ** GAMMA
}

function fromLinear(value: number): number {
  const clamped = Math.min(1, Math.max(0, value))
  const encoded =
    clamped <= ENCODE_THRESHOLD
      ? clamped * LINEAR_SLOPE
      : GAMMA_SCALE * clamped ** (1 / GAMMA) - GAMMA_OFFSET
  return encoded * CHANNEL_MAX
}

type Triple = readonly [number, number, number]

function toOklab(color: Rgba): Triple {
  const r = toLinear(color.r)
  const g = toLinear(color.g)
  const b = toLinear(color.b)
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function fromOklab([lightness, a, b]: Triple, alpha: number): Rgba {
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** CUBE
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** CUBE
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** CUBE
  return {
    r: fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    g: fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    b: fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
    a: alpha,
  }
}

export function mixOklab(first: Rgba, second: Rgba, secondShare: number): Rgba {
  const one = toOklab(first)
  const two = toOklab(second)
  const keep = 1 - secondShare
  return fromOklab(
    [
      one[0] * keep + two[0] * secondShare,
      one[1] * keep + two[1] * secondShare,
      one[2] * keep + two[2] * secondShare,
    ],
    first.a * keep + second.a * secondShare,
  )
}

export function withAlpha(color: Rgba, alpha: number): Rgba {
  return { ...color, a: color.a * alpha }
}

export function over(front: Rgba, back: Rgba): Rgba {
  const a = front.a
  return {
    r: front.r * a + back.r * (1 - a),
    g: front.g * a + back.g * (1 - a),
    b: front.b * a + back.b * (1 - a),
    a: 1,
  }
}

export function relativeLuminance(color: Rgba): number {
  return 0.2126 * toLinear(color.r) + 0.7152 * toLinear(color.g) + 0.0722 * toLinear(color.b)
}

export function ratioOf(front: Rgba, back: Rgba): number {
  const solidBack =
    back.a < 1 ? over(back, { r: CHANNEL_MAX, g: CHANNEL_MAX, b: CHANNEL_MAX, a: 1 }) : back
  const solidFront = front.a < 1 ? over(front, solidBack) : front
  const one = relativeLuminance(solidFront)
  const two = relativeLuminance(solidBack)
  return (Math.max(one, two) + 0.05) / (Math.min(one, two) + 0.05)
}

export function percentOf(text: string): number | null {
  const value = Number.parseFloat(text)
  return Number.isNaN(value) ? null : value / PERCENT
}
