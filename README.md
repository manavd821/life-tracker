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

## Demo data

`apps/backend/scripts/seed_demo_data.py` fills one existing user with ~42 days
of deterministic history (activity labels, context tags, behaviors, tasks and
their tag mappings) so the analytics, task analysis, pattern, AI insight and
chat engines have something to read. Nothing derived is stored — every metric is
still computed at request time. The user must have signed in once so the Clerk
webhook created the row.

```bash
cd apps/backend
uv run python -m scripts.seed_demo_data --clerk-user-id <clerk_user_id>
uv run python -m scripts.seed_demo_data --clerk-user-id <clerk_user_id> --reset   # replace it
```

Rows get deterministic IDs derived from the user, so `--reset` removes exactly
what a previous run created and leaves any real data alone; both the seed and
the reset commit in one transaction. Optional flags: `--days` (14–365, default
42), `--seed` (changes the generated pattern), `--tz-offset-minutes` (defaults
to the local zone).

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
| `GET/POST` | `/api/tasks?date=&tz_offset_minutes=` | List one day's tasks (interval overlap) / create |
| `GET/PATCH/DELETE` | `/api/tasks/{id}` | Read / update / delete a task |
| `GET` | `/api/tasks/analysis?date=&tz_offset_minutes=` | Completion for every task, or for one day when `date` is given |
| `GET` | `/api/tasks/{id}/analysis` | Completion plus contributing behaviors |
| `GET` | `/api/analytics/daily?date=&tz_offset_minutes=` | Aggregated daily metrics |
| `GET` | `/api/patterns/transitions?start_date=&end_date=` | Category and activity transitions |
| `GET` | `/api/patterns/context?start_date=&end_date=` | Activity/context duration associations |

Overlapping behaviors return `409` with the conflicting entries under
`error.conflicts`. Tasks are plans and may overlap each other.

## Task analysis

Completion is derived, never stored and never set by the user. Each behavior
overlapping a task is scored, then its overlap with the task window is
multiplied by that score:

| Match | Score |
| --- | --- |
| Category and activity label match | 1.0 |
| Category matches, activity label differs or is unset | 0.5 |
| Any shared context tag | +0.25 |
| Different category | 0 (no contribution) |

The score is capped at `1.0`. Behaviors cannot overlap each other and the score
is at most `1.0`, so effective minutes can never exceed planned minutes.

```text
Task 09:00–12:00 Study · DSA   planned 180 min

09:00–10:00 Study · OS   60 × 0.5 = 30
10:00–11:00 Study · DSA  60 × 1.0 = 60
11:00–12:00 Study · CN   60 × 0.5 = 30

effective 120 / 180 = 66.7%
```

Only the overlap with the task window counts, so time outside the planned
interval never contributes. Analysis is computed on request from `tasks` and
`behaviors`; when it becomes expensive it can move behind the same service
without changing the domain.

## Analytics

`GET /api/analytics/daily` returns objective aggregation only. It does not
detect patterns, interpret behaviour, or produce recommendations — that is a
separate layer which will consume these figures.

```text
Behaviors + Tasks  ──►  AnalyticsService  ──►  objective facts  ──►  dashboard
```

Behavior totals are grouped by PostgreSQL rather than in Python. A behavior is
counted toward a day when it overlaps that day's window, and only the overlapping
part is summed:

```sql
sum(floor(extract(epoch from least(end_time, day_end) - greatest(start_time, day_start)) / 60))
```

That clipping matters for behaviors that cross midnight: the 60 minutes that fall
inside the day are counted on that day, and the other 60 on the next one.

Unaccounted time is the remainder of the day, so it is never confused with a
recorded `Rest` behavior:

```text
unaccounted = day_minutes - tracked_minutes
```

Task figures come from `TaskAnalysisService`, never from a second implementation
of the scoring rules. The dashboard's completion rate is the weighted
`effective / planned` across the day's tasks, not the mean of per-task rates.

## Patterns

```text
Behaviors  ──►  PatternDetectionService  ──►  deterministic counts  ──►  facts
```

`PatternDetectionService` produces objective observations only. It never
interprets behaviour and never suggests an action — that is the Insight layer,
and AI coaching sits above that.

Transitions are counted between behaviors that touch in time. A gap of
unaccounted time breaks the chain, so `Study 09:00–10:00`, an unaccounted hour,
`Entertainment 11:00–12:00` never records `Study → Entertainment`. Consecutive
behaviors sharing a category collapse into a single step, so
`Study/DSA → Study/CN → Entertainment` gives one `Study → Entertainment`
transition while the activity level still sees `DSA → CN`.

```text
count(Study → Entertainment) / all transitions starting from Study = 0.621
```

Behaviors without an `ActivityLabel` take part in category transitions and break
the activity chain instead of being given an invented name.

`/api/patterns/context` describes each activity/context bucket — environment,
energy level, focus state, emotion state — with its session count, total minutes
and average, then compares the longest against the shortest average per bucket.
That comparison is an observed association only:

```text
CN + Library   8 sessions   avg 96 min
CN + Home      7 sessions   avg 48 min
```

Nothing here is a significance test, a correlation coefficient, or a causal
claim. Patterns are only surfaced once a threshold is met, configured with
`PATTERN_MIN_TRANSITION_COUNT` (default 5) and `PATTERN_MIN_CONTEXT_SESSIONS`
(default 3); the effective thresholds are returned with every response.
