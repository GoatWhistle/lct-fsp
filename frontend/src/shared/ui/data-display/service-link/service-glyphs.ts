import { CORE_SERVICE_GLYPHS } from "./service-glyphs-core"
import { EXTRA_SERVICE_GLYPHS } from "./service-glyphs-extra"
import type { ServiceId } from "./service-registry"

export type ServiceGlyph = { viewBox: string; path: string }

export const SERVICE_GLYPHS = {
  ...CORE_SERVICE_GLYPHS,
  ...EXTRA_SERVICE_GLYPHS,
} as Record<ServiceId, ServiceGlyph>
