# Correlation-Based Root Cause Analysis

How InferSight explains an anomaly by finding the other datasets in the same
organization that moved with it — the "related signals" feature.

## Feature summary

Given a dataset and one of its detected anomalies, the backend re-detects the
anomalies, computes a Pearson correlation between the anomaly dataset's series
and every sibling dataset's series around the anomaly timestamp, and returns up
to five ranked candidates with a `same` / `opposite` direction. Results are
cached per (dataset, anomaly, user) and rendered in the dashboard next to the
chart and inside AI insight cards.

## Endpoint

`backend/app/api/v1/intelligence.py:355`

```
GET /api/v1/intelligence/{dataset_id}/anomalies/{anomaly_id}/related
```

- `anomaly_id` is the **zero-based index** of the anomaly within the dataset's
  detection result (`GET /anomalies/datasets/{dataset_id}`), not a primary key.
- Requires at least 6 data points, otherwise `422`.
- The index is validated against the re-run detection result; out-of-range
  returns `404`.
- Response is a **bare array** of `RelatedSignalOut`
  `{dataset_id, dataset_name, correlation, direction}` (no wrapper object).
- Result is cached for 10 minutes keyed on
  `rel:{sha1(dataset_id|anomaly_id|user.id)}` (`cache_get_json` /
  `cache_set_json(..., ttl=600)`).

Access control: uses the same dataset read-access path as the rest of the
intelligence router (`_load_dataset`), and the cache key is per-user so one
user's result is never served to another.

## Detection and scoring

`find_related_datasets(anomaly, db_session)` in
`backend/app/services/analytics_service.py:209`:

1. **Anchor** — the anomaly's `dataset_id` and UTC timestamp.
2. **Own window** — pull the anomaly dataset's `MetricPoint`s within
   `_CORRELATION_WINDOW_PERIODS` periods of the anomaly timestamp (window length
   depends on the dataset's granularity).
3. **Candidates** — every other dataset in the same organization.
4. **Align** — each candidate's window is aligned to the anchor series by
   **nearest timestamp**, with a tolerance equal to the coarser of the two
   datasets' granularity period.
5. **Score** — Pearson correlation over the aligned pairs. Candidates with fewer
   than `_CORRELATION_MIN_OVERLAP` aligned points, or `|r| <= 0.6`, are
   discarded.
6. **Rank** — sort by `abs(correlation)` descending, take the top
   `_CORRELATION_MAX_RESULTS` (5).
7. **Direction** — `same` when `r >= 0`, else `opposite`.

### Constants (`backend/app/services/analytics_service.py:20-25`)

| Constant | Value |
|---|---|
| `_GRAN_SECONDS` | `hour: 3600`, `day: 86400`, `week: 604800`, `month: 2629800` |
| `_CORRELATION_WINDOW_PERIODS` | `hour: 24`, `day: 10`, `week: 8`, `month: 6` |
| `_CORRELATION_MIN_OVERLAP` | 5 |
| `_CORRELATION_THRESHOLD` | 0.6 |
| `_CORRELATION_MAX_RESULTS` | 5 |

### Related root-cause endpoint

`POST /api/v1/intelligence/{dataset_id}/root-cause` resolves the anomaly on the
requested date (or the strongest-scoring anomaly) and runs the same correlation
logic through `intelligence_service.root_cause`, producing the explanatory
payload used by the insight cards.

## Caching

`backend/app/services/cache.py` — `CacheService` is a facade over Redis with a
thread-safe `LocalTTLCache` fallback (default TTL 60s). If Redis is unreachable
or `REDIS_ENABLED=false`, the cache degrades silently and the endpoint still
works; the related-signals endpoint uses an explicit `600s` TTL.

## Frontend

- `frontend/src/components/RelatedSignalsPanel.tsx` — shared panel rendering each
  signal as a row: dataset name (link to its detail page), a 44px strength bar
  whose width is `|correlation|`, the mono correlation value (`toFixed(2)`), and
  a stroke-only direction icon (two up-arrows for `same`, up+down for
  `opposite`). Handles loading / "No related signals detected" states.
- `frontend/src/components/LineChart.tsx` — anomaly markers are clickable when a
  `datasetId` is provided; selecting one enlarges the marker and renders the
  related-signals panel below the chart with a close button. Selection resets
  when the dataset changes.
- `frontend/src/pages/Insights.tsx` — insight cards with an
  `anomaly_summary.total > 0` show a "See related signals" expander; on expand
  the page resolves the worst anomaly index (highest `|score|`) via
  `api.anomalies(dsId, 3, 7)` and renders the shared panel.
- `frontend/src/api/client.ts` — `getRelatedSignals(datasetId, anomalyId)`
  normalizes both the bare-array and `{related_signals: [...]}` response shapes.

## Tests

`backend/tests/test_related_signals.py` seeds an organization with the anomaly
dataset plus `same` / `opposite` / weak / sparse sibling datasets and asserts:

- highly correlated (`same`) datasets are returned with the correct direction;
- inversely correlated datasets are returned with `opposite`;
- weak-correlation (near zero-variance) and sparse-overlap candidates are
  discarded;
- out-of-organization datasets are never included;
- the `/related` endpoint returns the expected shape and the root-cause
  integration resolves.

```bash
python -m pytest backend/tests/test_related_signals.py -q
```

## Known caveats

- **Alignment is nearest-timestamp, not lagged** — the Pearson score compares
  point-to-point, so lead/lag relationships are treated as weaker correlations
  rather than explicitly detected offsets.
- **Organization-scoped** — datasets without an `organization_id` produce no
  related signals, and candidates are limited to the anomaly dataset's
  organization.
- **Cache is per-user** — two users in the same org recompute independently
  (correctness over cache hit rate).
