# Alert Routing & Escalation

How InferSight turns detected anomalies into durable in-app alerts, routes them
over per-dataset rules, delivers them asynchronously, and re-triggers delivery
for unacknowledged critical alerts.

## Feature summary

1. **Persist** — anomaly detections become `Alert` feed rows, deduplicated.
2. **Route** — each new alert is matched against the dataset's active `AlertRule`s
   (severity threshold + channels + cooldown); one `AlertDelivery` row is created
   per matching channel and its Celery task is enqueued.
3. **Deliver** — Celery workers execute each delivery over email / Slack / webhook
   and record the outcome (`sent` / `failed`) with a server-side error message.
4. **Escalate** — a 5-minute Beat job re-routes critical alerts that are still
   unread and whose rule cooldown has elapsed.

## Data model

Defined in `backend/app/models/alert.py`.

| Model | Table | Purpose |
|---|---|---|
| `Alert` | `alerts` | In-app feed entry (title, body, severity, `is_read`). Deduplicated via unique `(dataset_id, kind, title)`. |
| `AlertRule` | `alert_rules` | Routing config for one dataset: severity threshold, channel list, cooldown, active flag, optional per-rule `webhook_url`. |
| `AlertDelivery` | `alert_deliveries` | One delivery attempt of an alert over one channel; `rule_id` links it back for cooldown + escalation scoping. |

Enums: `SeverityLevel` (`warning`, `critical`), `AlertChannel` (`email`, `slack`,
`webhook`), `DeliveryStatus` (`pending`, `sent`, `failed`).

## API surface

Router file: `backend/app/api/v1/alert_rules.py`.

| Method | Path | Auth / RBAC | Notes |
|---|---|---|---|
| `POST` | `/api/v1/alert-rules` | dataset **write** access | Create rule (201). |
| `GET` | `/api/v1/alert-rules` | dataset **read** access | Paginated; optional `dataset_id` filter; only rules on readable datasets. |
| `PATCH` | `/api/v1/alert-rules/{id}` | dataset **write** access | Partial update (`exclude_unset=True` — safe to omit `webhook_url`). |
| `DELETE` | `/api/v1/alert-rules/{id}` | dataset **write** access | Deletes rule + its deliveries. |
| `GET` | `/api/v1/alerts/{alert_id}/deliveries` | alert **owner** only | Paginated delivery history for one alert. |

Access control reuses the existing `dataset_service.require_write_access` /
`rbac_service.can_read_dataset` helpers — no parallel auth mechanism. Write
operations on rules owned by a dataset a user cannot write return `403`;
deliveries for another user's alert return `403`.

### Request schemas (`backend/app/schemas/alert_rules.py`)

- `AlertRuleCreate` — `dataset_id` required; `severity_threshold` defaults to
  `warning`; `channels` defaults to `[email]` and must be non-empty (Pydantic
  validator); `cooldown_minutes` bounded `1..10080` (default 30); `webhook_url`
  optional, `max_length=512`.
- `AlertRuleUpdate` — all fields optional; same non-empty `channels` validator
  (only when provided). Apply via `model_dump(exclude_unset=True)`.
- All input is validated by Pydantic before touching the database; reads use
  SQLAlchemy parameterized queries only.

## Routing pipeline

1. `sync_alerts_from_anomalies` (`backend/app/services/alert_service.py:36`)
   skips alerts whose title already exists for the dataset (`Anomaly {direction}
   — {ts} UTC`, minute precision → same-minute duplicates collapse), persists the
   `Alert`, then calls `route_alert`. Routing failures are logged server-side and
   never abort the sync.
2. `route_alert` (`backend/app/services/anomaly_service.py:193`) iterates the
   dataset's **active** rules and, for each rule whose severity threshold is at
   or below the alert severity (`_matches_severity`, `warning` < `critical`) and
   whose cooldown has elapsed (`_in_cooldown`, based on the last `SENT` delivery
   for that rule), creates one `AlertDelivery` per channel and enqueues it.
3. `_enqueue_delivery` (`anomaly_service.py:176`) sends the channel's Celery task
   via `celery_app.send_task`. If `CELERY_ENABLED=false` or the broker is
   unreachable, it degrades gracefully (logs, leaves the delivery `PENDING`).

## Delivery execution

`deliver(db, alert_id, delivery_id)` in `backend/app/services/alert_delivery_service.py`:

- Loads the delivery + alert + dataset; unknown alert/dataset marks the delivery
  `failed` with a generic reason.
- Dispatches by channel. All external HTTP calls use an explicit `8s` timeout
  (`_HTTP_TIMEOUT`).
- Channel senders:
  - **email** — logging stub only (no SMTP configured). Returns success.
  - **slack** — `POST` to `settings.slack_webhook_url`; **fails closed** with a
    generic `"SLACK_WEBHOOK_URL is not configured"` if unset; non-2xx → failed.
  - **webhook** — `POST` to the rule's `webhook_url`; **fails closed** if unset;
    non-2xx → failed.
- Outcome is persisted: `sent` (sets `sent_at`, clears `error_message`) or
  `failed` (sets truncated `error_message`, max 1024 chars). Errors never leak
  stack traces or DB internals into responses; details are logged server-side.

## Celery wiring

- `backend/app/core/celery_app.py` — Celery app `infersight`; broker/result
  backend default to `settings.redis_url` (override with `CELERY_BROKER_URL`);
  JSON serializers, `timezone=UTC`; Beat schedule `escalate-critical-alerts`
  every `300.0s`.
- `backend/app/tasks.py` — `send_alert_email`, `send_alert_slack`,
  `send_alert_webhook`, and `escalate_critical_alerts` tasks; each opens its own
  `SessionLocal` and calls the delivery / escalation services.

### Escalation (`backend/app/services/anomaly_service.py:230`)

`escalate_critical_alerts(db, within_hours=24)` runs on the Beat schedule and
re-routes alerts that are **critical**, **not read** (`is_read = False`), and
created within the last 24h, re-applying the same severity + cooldown logic.
Returns `{critical_alerts, deliveries_created, skipped_in_cooldown}`.

## Configuration

Settings in `backend/app/config/settings.py` (all env-driven):

| Env var | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker/backend when `CELERY_BROKER_URL` unset. |
| `REDIS_ENABLED` | `true` | Master switch; cache falls back to in-process TTL when unreachable. |
| `CELERY_BROKER_URL` | `""` | Dedicated broker; falls back to `REDIS_URL`. |
| `CELERY_ENABLED` | `true` | If `false`, deliveries stay `PENDING` (rows still created). |
| `SLACK_WEBHOOK_URL` | `""` | Incoming webhook for the Slack channel. |

## Frontend

- `frontend/src/components/AlertRulesPanel.tsx` — rule rows with severity pills,
  channel badges, mono cooldown, active toggle, edit/delete (confirm), and an
  expandable **Delivery log** per alert showing channel, status pill
  (`pending`/`sent`/`failed`), timestamp, and error message.
- `frontend/src/pages/DatasetDetail.tsx` — the `alert-rules` tab renders the panel.
- `frontend/src/api/client.ts` / `types.ts` — `createAlertRule`,
  `listAlertRules(dataset_id?)`, `updateAlertRule`, `deleteAlertRule`,
  `listAlertDeliveries`, plus `AlertRule*` / `AlertDeliveryOut` types, via the
  existing `request<T>` client (Bearer auth + 401 refresh).

## Tests

`backend/tests/test_alert_rules.py` covers rule CRUD + validation, owner/write
scoping, cooldown behavior, routing/dedup, and delivery status transitions.
Run with the rest of the suite:

```bash
python -m pytest backend/tests -q
```

## Known caveats

- **"Unacknowledged" is modeled as `is_read = False`** — there is no separate
  ack flag, so reading an alert also stops escalation. A distinct ack concept
  would be a small model/API addition.
- **Email channel is a logging stub** — no SMTP integration; deliveries are
  recorded as `sent`.
- **Slack / webhook fail closed** without their URL configured (no silent drops).
- **PENDING deliveries whose Celery enqueue failed** (broker down) are not
  automatically retried; only the escalation Beat re-creates deliveries (and only
  for unread critical alerts).
