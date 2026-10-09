import type { ReactNode, SVGProps } from "react"

export type GlyphProps = SVGProps<SVGSVGElement>

const NODE_RADIUS = 1.75

function Node({ x, y, hollow = false }: { x: number; y: number; hollow?: boolean }) {
  return (
    <circle
      cx={x}
      cy={y}
      r={NODE_RADIUS}
      fill={hollow ? "none" : "currentColor"}
      stroke={hollow ? "currentColor" : "none"}
    />
  )
}

function glyph(children: ReactNode) {
  return function BrandGlyph(props: GlyphProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        {...props}
      >
        {children}
      </svg>
    )
  }
}

export const BackendGlyph = glyph(
  <>
    <rect x="4" y="4.5" width="16" height="6.5" rx="2" />
    <rect x="4" y="13" width="16" height="6.5" rx="2" />
    <path d="M12 7.75h4M12 16.25h4" />
    <Node x={8} y={7.75} />
    <Node x={8} y={16.25} />
  </>,
)

export const FrontendGlyph = glyph(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 8.5h18M7 15h5" />
    <Node x={15} y={15} />
  </>,
)

export const DataGlyph = glyph(
  <>
    <path d="M7.2 15.4 10.8 8.6M13.3 8.4l3.6 5.2M8.4 17.2l7.4-1.1" />
    <Node x={6} y={17.5} />
    <Node x={12} y={6.5} />
    <Node x={18} y={15.5} />
  </>,
)

export const QaGlyph = glyph(
  <>
    <path d="M4.5 12.5 9 17 16.6 8.4" />
    <Node x={18} y={6.8} />
  </>,
)

export const DevopsGlyph = glyph(
  <>
    <path d="M12 12c-1.8-2.6-3.6-4-5.6-4a4 4 0 0 0 0 8c2 0 3.8-1.4 5.6-4s3.6-4 5.6-4a4 4 0 0 1 0 8c-2 0-3.8-1.4-5.6-4" />
    <Node x={6.4} y={8} />
    <Node x={17.6} y={16} />
  </>,
)

export const FspGlyph = glyph(
  <>
    <path d="M10.9 5.6 6.1 15.4M13.1 5.6l4.8 9.8M7.8 17.5h8.4" />
    <Node x={12} y={4} />
    <Node x={5.5} y={17.5} />
    <Node x={18.5} y={17.5} />
  </>,
)

export const VerificationGlyph = glyph(
  <>
    <path d="M12 3 5 6v5.5c0 4.3 2.9 7.6 7 9.5 4.1-1.9 7-5.2 7-9.5V6l-7-3Z" />
    <Node x={12} y={11.5} />
  </>,
)

export const TestGlyph = glyph(
  <>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <path d="M12 9h3.5M12 15h3.5" />
    <Node x={8.75} y={9} />
    <Node x={8.75} y={15} hollow />
  </>,
)

export const TaskGlyph = glyph(
  <>
    <path d="m4 8 8-4 8 4v8l-8 4-8-4V8Z" />
    <path d="m4 8 8 4 8-4M12 13.75V20" />
    <Node x={12} y={12} />
  </>,
)

export const SelfReportGlyph = glyph(
  <>
    <path d="M4.5 19.5 5.6 15 15.2 5.4a2 2 0 0 1 2.8 0l.6.6a2 2 0 0 1 0 2.8L9 18.4l-4.5 1.1Z" />
    <path d="m13.5 7 3.5 3.5" />
    <Node x={19} y={19} hollow />
  </>,
)

export const MeasureGlyph = glyph(
  <>
    <path d="M3 17h18M6 17v-2.5M10 17v-1.5M14 17v-2.5M18 17v-1.5M11 8.75v6" />
    <Node x={11} y={7} />
  </>,
)

export const UncertaintyGlyph = glyph(
  <>
    <rect x="4" y="9.5" width="16" height="5" rx="2.5" />
    <path d="M12 5v2.5M12 16.5V19" />
    <Node x={12} y={12} />
  </>,
)

export const MatchGlyph = glyph(
  <>
    <path d="M7.6 16.2C8.4 11 10.6 12 12 12s3.6 1 4.4-4.2" />
    <Node x={6} y={18} />
    <Node x={18} y={6} />
  </>,
)

export const InvitationGlyph = glyph(
  <>
    <rect x="3" y="6" width="18" height="13" rx="2" />
    <path d="m3.5 7.5 8.5 6 8.5-6" />
    <Node x={12} y={13.5} />
  </>,
)

export const ApplicationGlyph = glyph(
  <>
    <path d="M7 12h11.5M14 7.5l4.5 4.5-4.5 4.5" />
    <Node x={5.25} y={12} />
  </>,
)

function gradeGlyph(filled: number) {
  const positions = [4.5, 9.5, 14.5, 19.5]
  return glyph(
    <>
      <path d="M6.25 12h1.5M11.25 12h1.5M16.25 12h1.5" />
      {positions.map((x, index) => (
        <Node key={x} x={x} y={12} hollow={index >= filled} />
      ))}
    </>,
  )
}

export const GradeOneGlyph = gradeGlyph(1)
export const GradeTwoGlyph = gradeGlyph(2)
export const GradeThreeGlyph = gradeGlyph(3)
export const GradeFourGlyph = gradeGlyph(4)
