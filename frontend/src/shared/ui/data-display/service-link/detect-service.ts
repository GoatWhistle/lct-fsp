import { type ServiceDefinition, serviceForDomain } from "./service-registry"

const SECURE_SCHEME = "https:"
const AUTHORITY = "/".repeat(2)
const ALLOWED_SCHEMES = new Set(["http:", SECURE_SCHEME])
const SCHEME_PREFIX = /^[a-z][a-z0-9+.-]*:/i

export function normalizeLinkUrl(raw: string): URL | null {
  const trimmed = raw.trim()
  if (trimmed === "") return null

  const schemeless = !SCHEME_PREFIX.test(trimmed)
  if (schemeless && (trimmed.startsWith("/") || !trimmed.includes("."))) return null

  let parsed: URL
  try {
    parsed = new URL(schemeless ? `${SECURE_SCHEME}${AUTHORITY}${trimmed}` : trimmed)
  } catch {
    return null
  }
  if (!ALLOWED_SCHEMES.has(parsed.protocol)) return null
  if (parsed.hostname === "") return null
  if (schemeless && !parsed.hostname.includes(".")) return null
  return parsed
}

export function linkHostname(raw: string): string | null {
  const parsed = normalizeLinkUrl(raw)
  if (parsed === null) return null
  const host = parsed.hostname.toLowerCase().replace(/\.+$/, "")
  return host.startsWith("www.") ? host.slice(4) : host
}

export function detectService(raw: string): ServiceDefinition | null {
  const host = linkHostname(raw)
  if (host === null) return null

  const labels = host.split(".")
  for (let i = 0; i < labels.length - 1; i += 1) {
    const candidate = labels.slice(i).join(".")
    const service = serviceForDomain(candidate)
    if (service !== null) return service
  }
  return null
}
