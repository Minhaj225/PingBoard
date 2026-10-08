# Start PingBoard

This guide starts PingBoard for local development. The Docker path is recommended because it starts the frontend, API, PostgreSQL, Redis, and background worker together.

## 1. Check prerequisites

Install and start:

- Docker Engine or Docker Desktop
- Docker Compose plugin (`docker compose`)
- A web browser

From the repository root, confirm Docker works:

```bash
docker --version
docker compose version
```

## 2. Create the environment file

Run this once:

```bash
cp .env.example .env
```

Open `.env` and replace `JWT_SECRET` with a random value at least 32 characters long. For example:

```bash
openssl rand -hex 32
```

Paste the generated value after `JWT_SECRET=`. The default local ports are:

- Frontend: `5173`
- API: `8000`
- PostgreSQL: `5433`
- Redis: `6380`

## 3. Start the app with Docker

From the repository root:

```bash
docker compose up --build -d
```

The first build can take a few minutes. Later starts are faster.

Check that every service is running:

```bash
docker compose ps
```

The `api` and database/Redis services should show as healthy. The `web` and `worker` services should show as running.

## 4. Open PingBoard

Open the frontend:

<http://localhost:5173>

Useful endpoints:

| Purpose            | URL                                |
| ------------------ | ---------------------------------- |
| PingBoard frontend | http://localhost:5173              |
| API documentation  | http://localhost:8000/docs         |
| API liveness       | http://localhost:8000/health       |
| API readiness      | http://localhost:8000/health/ready |

Do not use `http://localhost:8000/` as the app page. The API root has no route and returning `404 Not Found` there is expected.

## 5. Create an account

1. Open <http://localhost:5173/register>.
2. Enter your name, email, and a password with at least 12 characters.
3. After registration, create an organization if prompted.
4. Create a monitor with a publicly reachable URL, such as `https://example.com`.

The background worker checks active monitors automatically. It wakes every 10 seconds to find due monitors, while each monitor runs according to its configured interval. Keep the `worker` container running for automatic checks.

## 6. Watch logs

View all service logs:

```bash
docker compose logs -f
```

View only the worker:

```bash
docker compose logs -f worker
```

A successful scheduled check includes log messages for `scheduler_tick` and `run_monitor_check`.

## 7. Stop and restart

Stop the containers but keep database data:

```bash
docker compose down
```

Start them again without rebuilding:

```bash
docker compose up -d
```

Stop the stack and delete local PostgreSQL and Redis data. This permanently deletes local accounts, organizations, monitors, and check history:

```bash
docker compose down -v
```

## Troubleshooting

### Port already allocated

Another process is using a configured port. Change `API_PORT`, `WEB_PORT`, `POSTGRES_PORT`, or `REDIS_PORT` in `.env`, then restart:

```bash
docker compose down
docker compose up --build -d
```

### Frontend shows a server or API error

Check readiness:

```bash
curl http://localhost:8000/health/ready
```

A working response looks like:

```json
{ "status": "ok", "database": true, "redis": true }
```

Then inspect the API logs:

```bash
docker compose logs --tail=100 api
```

### A monitor stays pending

The API container does not perform checks. The separate worker does. Confirm it is running:

```bash
docker compose ps worker
docker compose logs --tail=100 worker
```

Restart it if needed:

```bash
docker compose restart worker
```

Refresh the monitor page after the first scheduled check completes.

### Browser reports a CSP warning from `content.js`

A `content.js` CSP warning usually comes from a browser extension. It is not a PingBoard server error. Test in a private window or with extensions disabled if the warning is distracting.

### API root returns `Not Found`

Use the frontend at <http://localhost:5173>. The API is intended to serve endpoints such as `/health`, `/docs`, and `/auth/register`; it does not serve a page at `/`.

## Optional: run the app without Docker

The native path still requires PostgreSQL and Redis. The simplest setup is to run only those two dependencies with Docker, while running the application processes directly.

Start the dependencies:

```bash
docker compose up -d --wait db redis
```

In terminal 1, start the API:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
set -a
source ../.env
set +a
alembic upgrade head
uvicorn app.main:app --reload
```

In terminal 2, start the frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

In terminal 3, start the worker. This is required for automatic monitor checks:

```bash
cd backend
source .venv/bin/activate
set -a
source ../.env
set +a
arq app.workers.main.WorkerSettings
```

Then open <http://localhost:5173>.

## Useful development checks

Run backend checks inside the API container:

```bash
docker compose exec api ruff check .
docker compose exec api mypy app
docker compose exec api pytest
```

Run frontend checks inside the web container:

```bash
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm run test
docker compose exec web npm run build
```
