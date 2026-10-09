import { clsx } from "clsx"
import { type CSSProperties, useId, useRef } from "react"
import { ArtRings } from "./art-rings"
import { ArtTraces } from "./art-traces"
import styles from "./brand-art.module.css"
import { usePointerTilt } from "./use-pointer-tilt"

const SCAN_TINT = "0.08 0.16 0.03 0 0 0.06 0.12 0.02 0 0 0.3 0.6 0.1 0 0 1.35 2.7 0.45 0 -1.6"

export interface BrandArtProps {
  readonly className?: string | undefined
}

export function BrandArt({ className }: BrandArtProps) {
  const ref = useRef<HTMLElement>(null)
  const tint = useId()
  usePointerTilt(ref)
  return (
    <figure
      ref={ref}
      className={clsx(styles.art, className)}
      style={{ "--scan-filter": `url(#${CSS.escape(tint)})` } as CSSProperties}
      aria-hidden="true"
    >
      <svg className={styles.defs} aria-hidden="true">
        <filter id={tint} colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix" values={SCAN_TINT} />
          <feComposite in2="SourceGraphic" operator="in" />
        </filter>
      </svg>
      <ArtRings />
      <div className={styles.stage}>
        <div className={styles.head}>
          <img className={styles.face} src="/brand/face.webp" alt="" width={332} height={313} />
          <img className={styles.scan} src="/brand/face.webp" alt="" width={332} height={313} />
        </div>
      </div>
      <ArtTraces />
    </figure>
  )
}
