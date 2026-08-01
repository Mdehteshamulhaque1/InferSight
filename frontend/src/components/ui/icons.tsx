import type { ReactNode } from 'react'

export interface IconProps {
  size?: number
  className?: string
  strokeWidth?: number
}

function base(size: number, className: string | undefined, children: ReactNode, sw = 1.6) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

const P = ({ size = 16, className, children }: IconProps & { children: ReactNode }) =>
  base(size, className, children)

export const IconDashboard = (p: IconProps) => (
  <P {...p}>
    <rect x="3" y="3" width="7.5" height="9" rx="1.6" />
    <rect x="13.5" y="3" width="7.5" height="5.5" rx="1.6" />
    <rect x="13.5" y="12" width="7.5" height="9" rx="1.6" />
    <rect x="3" y="15" width="7.5" height="6" rx="1.6" />
  </P>
)

export const IconDataset = (p: IconProps) => (
  <P {...p}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
    <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
  </P>
)

export const IconInsight = (p: IconProps) => (
  <P {...p}>
    <path d="M9 18h6" />
    <path d="M10 22h4" />
    <path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3h6c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2Z" />
  </P>
)

export const IconTrend = (p: IconProps) => (
  <P {...p}>
    <path d="M3 17l6-6 4 4 8-8" />
    <path d="M14 7h7v7" />
  </P>
)

export const IconLogout = (p: IconProps) => (
  <P {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5" />
    <path d="M21 12H9" />
  </P>
)

export const IconDownload = (p: IconProps) => (
  <P {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M7 10l5 5 5-5" />
    <path d="M12 15V3" />
  </P>
)

export const IconUpload = (p: IconProps) => (
  <P {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" />
    <path d="M12 3v12" />
  </P>
)

export const IconRefresh = (p: IconProps) => (
  <P {...p}>
    <path d="M21 12a9 9 0 1 1-2.6-6.4" />
    <path d="M21 3v6h-6" />
  </P>
)

export const IconPlus = (p: IconProps) => (
  <P {...p}>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </P>
)

export const IconTrash = (p: IconProps) => (
  <P {...p}>
    <path d="M3 6h18" />
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
  </P>
)

export const IconBell = (p: IconProps) => (
  <P {...p}>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </P>
)

export const IconChat = (p: IconProps) => (
  <P {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    <path d="M8 9h8" />
    <path d="M8 13h5" />
  </P>
)

export const IconHealth = (p: IconProps) => (
  <P {...p}>
    <path d="M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6c-2.5 4.5-9.5 9-9.5 9Z" />
    <path d="M7.5 12h3l1.5-2.5 2 4 1.5-1.5h1" />
  </P>
)

export const IconClock = (p: IconProps) => (
  <P {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </P>
)

export const IconShield = (p: IconProps) => (
  <P {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    <path d="M9 12l2 2 4-4" />
  </P>
)

export const IconSearch = (p: IconProps) => (
  <P {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </P>
)

export const IconArrowRight = (p: IconProps) => (
  <P {...p}>
    <path d="M5 12h14" />
    <path d="M13 6l6 6-6 6" />
  </P>
)

export const IconArrowLeft = (p: IconProps) => (
  <P {...p}>
    <path d="M19 12H5" />
    <path d="M11 18l-6-6 6-6" />
  </P>
)

export const IconChevronDown = (p: IconProps) => (
  <P {...p}>
    <path d="m6 9 6 6 6-6" />
  </P>
)

export const IconChevronRight = (p: IconProps) => (
  <P {...p}>
    <path d="m9 6 6 6-6 6" />
  </P>
)

export const IconClose = (p: IconProps) => (
  <P {...p}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </P>
)

export const IconCheck = (p: IconProps) => (
  <P {...p}>
    <path d="M20 6 9 17l-5-5" />
  </P>
)

export const IconCheckCircle = (p: IconProps) => (
  <P {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12.5 2.5 2.5 4.5-5" />
  </P>
)

export const IconAlertCircle = (p: IconProps) => (
  <P {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4" />
    <path d="M12 16h.01" />
  </P>
)

export const IconMenu = (p: IconProps) => (
  <P {...p}>
    <path d="M4 6h16" />
    <path d="M4 12h16" />
    <path d="M4 18h16" />
  </P>
)

export const IconCommand = (p: IconProps) => (
  <P {...p}>
    <path d="M9 9V6a3 3 0 1 0-3 3h16" />
    <path d="M15 9V6a3 3 0 1 1 3 3H4" />
    <path d="M9 15v3a3 3 0 1 0 3-3H4" />
    <path d="M15 15v3a3 3 0 1 1-3-3h16" />
  </P>
)

export const IconSparkles = (p: IconProps) => (
  <P {...p}>
    <path d="M12 3l1.8 4.6L18.4 9.4l-4.6 1.8L12 15.8l-1.8-4.6L5.6 9.4l4.6-1.8L12 3Z" />
    <path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
    <path d="M5 16l.7 1.6L7.3 18.3l-1.6.7L5 20.6l-.7-1.6L2.7 18.3l1.6-.7L5 16Z" />
  </P>
)

export const IconEye = (p: IconProps) => (
  <P {...p}>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </P>
)

export const IconEyeOff = (p: IconProps) => (
  <P {...p}>
    <path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18.4 18.4 0 0 1-2.2 3.2" />
    <path d="M6.6 6.6C3.7 8.4 2 12 2 12s3.5 8 10 8a9.7 9.7 0 0 0 5.4-1.6" />
    <path d="M9.9 9.9a3.5 3.5 0 0 0 4.2 4.2" />
    <path d="m2 2 20 20" />
  </P>
)

export const IconFile = (p: IconProps) => (
  <P {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
    <path d="M14 2v6h6" />
  </P>
)

export const IconSpark = (p: IconProps) => (
  <P {...p}>
    <path d="m12 2 1.4 5.1L18.5 8.5l-5.1 1.4L12 15l-1.4-5.1L5.5 8.5l5.1-1.4L12 2Z" />
    <path d="M5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Z" />
    <path d="M19 13l.6 1.7 1.7.6-1.7.6L19 17.6l-.6-1.7-1.7-.6 1.7-.6L19 13Z" />
  </P>
)

export const IconDatabase = (p: IconProps) => (
  <P {...p}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </P>
)

export const IconFlag = (p: IconProps) => (
  <P {...p}>
    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1Z" />
    <path d="M4 22v-7" />
  </P>
)

export const IconActivity = (p: IconProps) => (
  <P {...p}>
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </P>
)
