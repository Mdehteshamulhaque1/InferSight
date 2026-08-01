# InferSight — Frontend

React + TypeScript dashboard for the InferSight analytics API, built to the visual language in `../DESIGN.md` (navy ink, indigo primary, pill buttons, weight-300 type, tabular figures, dark app shell).

## Run

```bash
npm install
npm run dev        # http://localhost:5173 — proxies /api to backend on :8000
```

The backend must be running first:

```bash
cd ../backend
uvicorn app.main:app --reload --port 8000
```

Sign in with the seeded demo account (`demo@infersight.dev` / `demo12345`) or register a new one.

## Build

```bash
npm run build      # tsc --noEmit + vite build -> dist/
```

## Structure

```
src/
├── api/           # typed API client + response types (auto refresh-token rotation on 401)
├── auth/          # auth context (tokens in localStorage, /me bootstrap)
├── components/    # layout shell, toast, gradient mesh, custom SVG LineChart
├── hooks/         # useAsync data-fetching hook
├── pages/         # Dashboard, Datasets, Insights, Login, Register
└── styles/        # design tokens (global.css)
```

Charts are hand-rolled SVG (`components/LineChart.tsx`): area + line for the series, dashed trend overlay, forecast confidence band, and ruby anomaly markers — no chart library dependency.
