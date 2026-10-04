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
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web | Clerk publishable key |
| `CLERK_SECRET_KEY` | web | Clerk secret key |

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
