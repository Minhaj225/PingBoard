# PingBoard

PingBoard is a multi-tenant uptime monitoring platform. An organization registers
monitors (a URL, a check interval and a set of assertions), a background worker
checks them on schedule, failures open incidents and notify the team over
email/Slack/Discord, and each org can publish a no-login public status page.

**Stack:** React + TypeScript + Tailwind · FastAPI (async) · PostgreSQL 16 · Redis 7 · ARQ · Docker · JWT/OAuth

## Architecture

```
                ┌──────────────┐
  browser ─────▶│  web (Vite)  │
                └──────┬───────┘
                       │  HTTPS / JSON
                ┌──────▼───────┐        ┌────────────┐
                │  api (FastAPI)├──────▶│  Postgres  │
                └──────┬───────┘        └─────▲──────┘
                       │  enqueue              │
                ┌──────▼───────┐               │
                │    Redis     │               │
                └──────┬───────┘               │
                       │  dequeue              │
                ┌──────▼───────┐               │
                │ worker (ARQ) ├───────────────┘
                └──────┬───────┘
                       │  HTTP checks / webhooks
                       ▼
             monitored targets · Slack · Discord · SMTP
```

The `api` and `worker` run the same image with different commands: the API never
performs outbound checks, and the worker never serves HTTP.

## Local setup

Requires Docker with the Compose plugin.

```bash
cp .env.example .env
# edit .env — at minimum set a real JWT_SECRET:
#   openssl rand -hex 32
docker compose up --build
```

| Service    | URL                            |
| ---------- | ------------------------------ |
| Frontend   | http://localhost:5173          |
| API        | http://localhost:8000          |
| API docs   | http://localhost:8000/docs     |
| Liveness   | http://localhost:8000/health   |
| Readiness  | http://localhost:8000/health/ready |

The frontend's landing page calls `/health` and renders the result, which
confirms the whole chain (browser → Vite → API → CORS) is wired up.

Postgres and Redis are published on **5433** and **6380** rather than their
standard ports, so the stack doesn't collide with a Postgres or Redis already
installed on the host. Override `POSTGRES_PORT` / `REDIS_PORT` in `.env` if
those are taken too; containers always reach each other on `db:5432` and
`redis:6379` regardless.

### Troubleshooting

**`PermissionError` reading files in `/app`** — on SELinux hosts (Fedora, RHEL)
bind mounts need the `:z` label, which `docker-compose.yml` already sets. If you
add a mount, label it too.

**Files created by containers are owned by root** — set `DOCKER_UID` /
`DOCKER_GID` in `.env` to your own (`id -u`, `id -g`) and rebuild; both images
take them as build args.

**`port is already allocated`** — something else holds the host port. Change
`POSTGRES_PORT`, `REDIS_PORT`, `API_PORT` or `WEB_PORT` in `.env`.

## Authentication

Sessions use a split-token scheme:

| | Access token | Refresh token |
| --- | --- | --- |
| Form | Signed JWT (HS256) | Opaque 64-byte random string |
| Lifetime | 15 minutes | 30 days |
| Where it lives | Client memory only | httpOnly `SameSite=Lax` cookie scoped to `/auth` |
| Server-side | Nothing stored | SHA-256 digest row, revocable |

The access token is deliberately kept out of `localStorage`: anything JavaScript
can read, injected script can read too. Because it lives only in memory, a page
reload starts with no token — the SPA silently calls `POST /auth/refresh`, which
the browser answers from the cookie it cannot itself read.

Refresh tokens are **single-use**. Every refresh revokes the presented token and
issues a new one, so a stolen cookie is only good until the legitimate client
refreshes next. Presenting an already-rotated token is treated as theft: every
outstanding session for that user is revoked and a warning is logged.

Passwords are bcrypt-hashed after a SHA-256 pre-hash, which sidesteps bcrypt's
72-byte truncation so long passphrases keep their full entropy.

`GET /auth/github/login` starts the GitHub authorization-code flow; the callback
sets the refresh cookie and redirects to the SPA, so no token is ever placed in a
URL. Leave `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` unset and the endpoints
return 503 — the rest of the app is unaffected.

## Roles

Every resource hangs off an organization, and access is decided by the caller's
membership, never by an `org_id` supplied in the request.

| Role | Can |
| --- | --- |
| `viewer` | Read the organization and its members |
| `admin` | …plus invite members (up to their own role) |
| `owner` | …plus everything, including granting `owner` |

Non-members get **404**, not 403: telling an outsider that an organization
exists is itself a disclosure.

## Monitors and the worker

A monitor is a URL, an interval and a set of assertions. The `worker` container
runs an ARQ scheduler that every 10s claims the monitors whose `next_run_at` has
passed, enqueues one job each, and advances their schedule.

Two details make that safe to scale past one worker:

- The claim uses `SELECT … FOR UPDATE SKIP LOCKED`, so each due monitor is handed
  to exactly one worker and contention never blocks.
- `next_run_at` advances **as part of the claim**, before the check runs. A
  worker that dies mid-check costs one missed data point rather than re-claiming
  the same monitor in a tight loop against someone else's server.

After an outage the scheduler catches up in a single hop rather than firing every
slot it missed — a monitor on a 30s interval that was unchecked for an hour runs
once, not 120 times.

### Flap protection

A monitor flips to `down` only after `DEFAULT_FAILURE_THRESHOLD` (3) consecutive
failures, so one blip does not raise an alarm. Recovery is immediate: the first
success restores `up` and resets the counter. Both transitions are edge-triggered,
which is what Phase 4 uses to open and resolve incidents exactly once.

### SSRF, twice

User-supplied URLs are validated on create, on update, **and again inside the
worker** just before the request. DNS can change between saving a monitor and
checking it; re-resolving at execution time is what closes the rebinding hole.

## Incidents and alerting

When a monitor crosses the failure threshold the worker opens an `Incident`;
when it recovers, the same edge closes it and appends an automatic "resolved"
entry. A partial unique index (`monitor_id WHERE resolved_at IS NULL`) means the
database — not application logic — guarantees at most one open incident per
monitor, so two workers racing cannot produce duplicates.

Notifications are **queued, never inline**. The checker enqueues a job and moves
on; a webhook that hangs for 30 seconds can't slow down monitoring. Delivery
fans out to every active channel, and one broken channel does not stop the
others. The single exception is `POST /channels/{id}/test`, which delivers
synchronously because someone configuring a webhook needs to know immediately
whether it works.

Webhook URLs are **bearer credentials** — anyone holding one can post into that
workspace. They are stored as given but masked on every read, so `GET /channels`
returns `https://hooks.slack.com/…` and never the secret path.

## Public status pages

`GET /public/status/{slug}` takes no auth dependency and returns a schema
written for that endpoint alone — never `MonitorRead`. A visitor sees a display
name, a traffic light and a 90-day bar; the target URL, every UUID, the
assertions and the check interval all stay private, and a new monitor field is
private by default rather than exposed by accident.

On the frontend the route sits **outside** `AuthLayout`, so an anonymous visitor
triggers no session bootstrap and no call to `/auth/refresh` at all.

A missing slug and an unpublished page return the same 404, so the endpoint
cannot be used to discover private slugs. Monitors added to a page are filtered
through the owning org, so a guessed id from another tenant is silently dropped
rather than published.

Uptime is aggregated in SQL (`generate_series` left-joined to a grouped count),
not by pulling raw rows into Python: a 90-day window on a 30-second monitor is
~250k rows to produce 90 numbers. Days with no checks render as explicit gaps
rather than disappearing, so a monitoring outage never masquerades as uptime.

## Scale and safety

**Rollups.** A worker job aggregates each closed hour of `check_results` into
one `rollups_hourly` row per monitor, upserted on `(monitor_id, hour)` so a
re-run after a crash recomputes rather than double-counting. `GET
/monitors/{id}/uptime` reads those rollups plus the still-open hour, which on a
30-day window over 43k raw rows cut buffer reads from 841 to 15.

Counts recombine exactly; **percentiles do not**. The reported p95 is the worst
hour's p95 — a deliberate over-estimate rather than a figure that looks exact
and is quietly wrong. For a true p95, query raw rows inside the retention
window.

**Retention.** A daily job prunes raw checks older than `RAW_RETENTION_DAYS`
(30), in batches, and only rows already covered by a rollup — so pruning can
never destroy history that was not summarised first. Beyond that window,
history remains at hourly resolution. Raise the setting if per-check forensics
matter more than table size.

**Caching.** Public status pages (30s) and uptime figures (60s) are cached in
Redis, TTL-only with no invalidation: these are continuously-changing aggregates
where a short staleness window is invisible. A Redis outage degrades to
"slower", never "broken" — every path falls back to computing the value.
Responses carry `X-Cache: HIT|MISS`.

**Rate limits.** Redis fixed-window counters, bucketed by client IP, with three
separate budgets: auth endpoints (10/min, tightest — these are the ones worth
brute-forcing), the public status endpoint (60/min), and authenticated writes
(120/min). A Redis failure fails *open* on purpose: losing a rate limiter must
not lock users out of signing in.

**API keys.** `pb_`-prefixed (greppable, scanner-detectable), shown exactly
once, stored only as a SHA-256 digest. A key authenticates as an admin of one
organization and is refused against any other, so `POST /monitors` is scriptable
from CI without a browser session. Revoking is a soft delete, keeping the audit
trail after the credential dies.

## Frontend

**One token system.** Every colour is a role — `surface`, `ink`, `line`, and the
reserved status colours `up`/`down`/`degraded`/`unknown` — defined once in
`index.css`. Dark mode is a second set of values for those same roles under
`[data-theme="dark"]`, not a second set of components, and the latency chart
follows it through `var()` in SVG fills. Status is always word + shape, never
colour alone, so it survives colour-blindness and forced-colours mode.

**Typed against the backend.** `src/api/schema.d.ts` is generated from the live
OpenAPI document (`npm run generate:api`) and `types.ts` aliases those schemas
rather than restating them — so a backend field that changes shape fails `tsc`
instead of breaking at runtime. Wiring this up immediately caught two fields the
hand-written types had wrongly assumed were always present.

Loading states are skeletons shaped like the content they replace, empty states
name the next action, an error boundary catches render crashes, and actions
raise toasts. The layout is checked at 390px with no horizontal overflow, and
`prefers-reduced-motion` is honoured.

## Migrations

`docker compose up` runs `alembic upgrade head` before starting the API. To
drive Alembic by hand:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "add monitors"
docker compose exec api alembic downgrade -1
```

## Development without Docker

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export $(grep -v '^#' ../.env | xargs)   # or use direnv
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Checks

```bash
# Backend
docker compose exec api ruff check .
docker compose exec api ruff format --check .
docker compose exec api mypy app
docker compose exec api pytest

# Frontend
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm run build
```

## Project layout

```
pingboard/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            # app factory + ASGI entrypoint
│  │  ├─ health.py          # liveness / readiness
│  │  ├─ core/              # config, db, redis, logging, security
│  │  ├─ auth/ orgs/ monitors/ incidents/ channels/ status_pages/
│  │  └─ workers/           # ARQ scheduler + job handlers (Phase 3)
│  ├─ alembic/              # async migration environment
│  └─ tests/
├─ frontend/
│  └─ src/{api,components,features,hooks,pages}
└─ docker-compose.yml
```

## Roadmap

Built phase by phase per `PingBoard_Implementation_Plan.md`.

- [x] **Phase 0** — scaffolding, `/health`, compose stack
- [x] **Phase 1** — auth & organizations
- [x] **Phase 2** — monitors CRUD & checker core
- [x] **Phase 3** — scheduler & background worker
- [x] **Phase 4** — incidents & alerting
- [x] **Phase 5** — public status pages
- [x] **Phase 6** — rollups, caching, rate limiting, API keys
- [x] **Phase 7** — frontend polish & UX
- [ ] Phase 8 — testing, CI/CD, deployment
