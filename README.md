# Life Tracker

## Requirements

- Node.js 20+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Neon PostgreSQL database
- A Clerk application

## Setup

Copy the example env files and fill them in:

```bash
cp apps/web/.env.example apps/web/.env
cp apps/backend/.env.example apps/backend/.env
```

| Variable | App | Description |
| --- | --- | --- |
| `DATABASE_URL` | backend | Neon PostgreSQL connection string |
| `CLERK_WEBHOOK_SECRET` | backend | Signing secret from the Clerk webhook endpoint |
| `CLERK_ISSUER` | backend | Clerk frontend API, e.g. `https://<subdomain>.clerk.accounts.dev` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web | Clerk publishable key |
| `CLERK_SECRET_KEY` | web | Clerk secret key |
| `BACKEND_API_URL` | web | Backend base URL, e.g. `http://127.0.0.1:8000` |

## Backend

```bash
cd apps/backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --loop app.db.session:loop_factory
```

On Windows the `--loop` flag is required: psycopg's async mode needs a selector
event loop, while uvicorn otherwise defaults to `ProactorEventLoop`. On Linux
and macOS you can drop the flag.

## Web

```bash
cd apps/web
npm install
npm run dev
```

## Clerk

1. Add the webhook endpoint in the Clerk dashboard under **Webhooks**:
   `https://<your-backend-host>/api/webhooks/clerk`, subscribed to
   `user.created`.
2. Copy the endpoint's signing secret into `CLERK_WEBHOOK_SECRET`.
3. Use a tunnel tool (ngrok, Cloudflare Tunnel) for local development so Clerk
   can reach your machine.

## Alembic

```bash
uv run alembic revision --autogenerate -m "message"   # after changing a model
uv run alembic upgrade head
uv run alembic current
uv run alembic check                                    # detect model/migration drift
```

## Tests

Tests run against a separate `lifetracker_test` database on the same Neon
project. Create it once, then point the suite at it:

```bash
cd apps/backend
createdb $TEST_DATABASE_URL     # any client works, name must be lifetracker_test
uv run pytest
```

Override the target with `TEST_DATABASE_URL` if you keep it somewhere else. The
suite applies migrations to that database and truncates between tests, so never
point it at `neondb`.

## API

All endpoints require `Authorization: Bearer <clerk session token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/behaviors` | Create a behavior |
| `GET` | `/api/behaviors?date=&tz_offset_minutes=` | Day timeline with gaps |
| `GET` | `/api/behaviors/{id}` | Fetch one behavior |
| `PATCH` | `/api/behaviors/{id}` | Update a behavior |
| `DELETE` | `/api/behaviors/{id}` | Soft delete a behavior |
| `GET/POST` | `/api/activity-labels` | List / create activity labels |
| `PATCH/DELETE` | `/api/activity-labels/{id}` | Update / delete a label |
| `GET/POST` | `/api/context-tags` | List / create context tags |
| `PATCH/DELETE` | `/api/context-tags/{id}` | Update / delete a tag |

Overlapping behaviors return `409` with the conflicting entries under
`error.conflicts`.
