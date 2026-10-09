export function anonymousId(id: string): string {
  return `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`
}
