import { clsx } from "clsx"
import { Icon } from "../../primitives/icon/icon"
import { detectService } from "./detect-service"
import { SERVICE_GLYPHS } from "./service-glyphs"
import styles from "./service-icon.module.css"

export interface ServiceIconProps {
  readonly href: string
  readonly className?: string | undefined
}

export function ServiceIcon({ href, className }: ServiceIconProps) {
  const service = detectService(href)
  if (service === null) return <Icon name="link" size="sm" className={className} />
  const glyph = SERVICE_GLYPHS[service.id]
  return (
    <svg
      viewBox={glyph.viewBox}
      fill="currentColor"
      aria-hidden="true"
      className={clsx(styles.glyph, className)}
    >
      <path d={glyph.path} />
    </svg>
  )
}

export function serviceLabel(href: string): string | null {
  return detectService(href)?.label ?? null
}
