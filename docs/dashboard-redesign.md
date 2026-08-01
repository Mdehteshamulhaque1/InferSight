# Dashboard Redesign

The visual-language overhaul of the InferSight frontend: a dark-slate
observability system with a single accent color, flat hairline surfaces, and
mono numerals — applied across the app shell, charts, alerts, insight cards,
and the marketing landing page.

## Design language

The system header in `frontend/src/styles/global.css` states the rules of the
road:

> Dark slate observability. Base `#0a0a0f`, panels `#14161c`, hairline borders,
> one accent (`#3b82f6`) reserved for critical severity, primary buttons, and
> active navigation. All numerals render in JetBrains Mono.

Key decisions:

- **One accent, used sparingly.** `#3b82f6` (with `-deep` `#2563eb`,
  `-press` `#1d4ed8`, `-soft` `#60a5fa`) is the only saturated color in the
  system. It marks critical severity, primary buttons, active navigation, and
  focus rings. Everything else is neutral slate.
- **Dark slate surfaces.** Canvas `#0a0a0f`, `#0d0f15`, panels `#14161c` /
  `#1a1d26`. Depth is communicated with 1px hairlines
  (`rgba(255,255,255,0.08)` / `0.16`), not big shadows (`--shadow-1: none`).
- **Mono numerics.** All numbers render in JetBrains Mono (`--font-mono`) via the
  `.num` utility — the quiet observability signal.
- **Legacy aurora aliases remapped.** The old `--cyan`, `--violet`, `--magenta`
  tokens now resolve to the accent so no consumer breaks while the palette
  collapses to one hue.

## Token system (`frontend/src/styles/global.css`)

| Group | Examples |
|---|---|
| Brand / accent | `--primary`, `--primary-deep/-press/-soft`, `--primary-tint` |
| Ink (text) | `--ink #e8eaf0`, `--ink-secondary #a2a8b6`, `--ink-mute #6f7587`, `--ink-faint #3f4452` |
| Surface | `--canvas #0a0a0f`, `--canvas-soft`, `--surface #14161c`, `--surface-2 #1a1d26`, `--hairline*` |
| Semantic | `--ruby #f87171` (error/critical), `--green #34d399` (sent/success), `--amber #fbbf24` (warning), `--info #60a5fa` |
| Type scale | `--t-2xs` 10px … `--t-hero` 64px; weights `--w-300` … `--w-800` |
| Fonts | `--font` Inter, `--font-display` Archivo, `--font-mono` JetBrains Mono |
| Spacing | `--sp-1` 4px … `--sp-16` 64px |
| Radii | `--r-xs` 3px … `--r-2xl` 16px, `--r-pill` 9999px (flat, minimal) |
| Elevation | `--shadow-1: none`; subtle dark shadows only at `--shadow-2+` for overlays |
| Motion / z-index | `--ease`/`--dur-*`; `--z-topbar` … `--z-toast` |

Component-level tokens derive from these (e.g. `.card` uses `--surface`,
`--hairline`, `--sp-4`; pills use the semantic tints like `--ruby-tint`,
`--green-tint`, `--amber-tint`).

## Where it's applied

- **App shell** — `frontend/src/components/Layout.tsx` sidebar/topbar chrome in
  the dark surfaces, active nav highlighted with the accent, hairline dividers.
- **Charts** — `frontend/src/components/LineChart.tsx` hand-rolled SVG: area +
  line for the series, dashed trend overlay, forecast confidence band, ruby
  anomaly markers, and (since the correlation feature) clickable markers that
  open the related-signals panel below the chart. No chart library dependency.
- **KPI cards** — mono `.num` values, count-up hook (`hooks/useCountUp.ts`).
- **Alerts feed & rules** — `pages/Alerts.tsx`, `components/AlertRulesPanel.tsx`
  with severity pills (`warning` = amber, `critical` = ruby) and delivery-status
  pills (`pending`/`sent`/`failed`).
- **Insight cards** — `pages/Insights.tsx` with the expandable related-signals
  section.
- **Modals & toasts** — `components/Modal.tsx` (overlay + panel on the z-scale)
  and `components/Toast.tsx` (accent/error variants).
- **Marketing** — `pages/Landing.tsx` minimal dark hero with the gradient `Mesh`
  backdrop (`components/Mesh.tsx`).
- **Document metadata** — `frontend/index.html` ships a dark inline SVG favicon
  (slate tile, mono sparkline stroke, accent endpoint dot) and
  `theme-color=#0a0a0f`.

## Files

- `frontend/src/styles/global.css` — token system + all component styles
  (`.card`, `.btn`, pills, `.switch`, `.rel-signal`, layout chrome, forms).
- `frontend/src/components/Layout.tsx`, `Toast.tsx`, `Modal.tsx`,
  `Mesh.tsx`, `LineChart.tsx`, `icons.tsx`, `AlertRulesPanel.tsx`,
  `RelatedSignalsPanel.tsx`.
- `frontend/src/pages/Dashboard.tsx`, `DatasetDetail.tsx`, `Alerts.tsx`,
  `Insights.tsx`, `Landing.tsx`, `Login.tsx`, `Register.tsx`.
- `frontend/index.html` — dark favicon + theme color + font loading
  (Inter / Archivo / JetBrains Mono).

## Verification

```bash
npm run build   # tsc --noEmit + vite build — strict TS, no chart library
```

The build is green after the redesign and every subsequent feature; the backend
suite (`python -m pytest backend/tests -q`) also passes.
