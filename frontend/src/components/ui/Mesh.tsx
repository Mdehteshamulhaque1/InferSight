export function Mesh() {
  return (
    <div className="mesh" aria-hidden="true">
      <svg viewBox="0 0 1440 420" preserveAspectRatio="xMidYMin slice">
        <defs>
          <linearGradient id="mesh-base" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--mesh-g1)" />
            <stop offset="52%" stopColor="var(--mesh-g2)" />
            <stop offset="100%" stopColor="var(--mesh-g3)" />
          </linearGradient>
          <radialGradient id="blob1" cx="0.22" cy="0.55" r="0.5">
            <stop offset="0%" stopColor="var(--mesh-b1)" />
            <stop offset="100%" stopColor="var(--mesh-b1)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="blob2" cx="0.5" cy="0.35" r="0.45">
            <stop offset="0%" stopColor="var(--mesh-b2)" />
            <stop offset="100%" stopColor="var(--mesh-b2)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="blob3" cx="0.78" cy="0.6" r="0.5">
            <stop offset="0%" stopColor="var(--mesh-b3)" />
            <stop offset="100%" stopColor="var(--mesh-b3)" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="wash" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--mesh-w0)" />
            <stop offset="100%" stopColor="var(--mesh-w1)" />
          </linearGradient>
        </defs>
        <rect width="1440" height="420" fill="url(#mesh-base)" />
        <circle cx="330" cy="250" r="260" fill="url(#blob1)" />
        <circle cx="720" cy="140" r="300" fill="url(#blob2)" />
        <circle cx="1130" cy="250" r="280" fill="url(#blob3)" />
        <rect width="1440" height="420" fill="url(#wash)" />
      </svg>
    </div>
  )
}
