# Architecture

## System Overview

Life Tracker is a full-stack application for tracking behaviors, tasks, and deriving insights. It follows a clean separation of concerns with:

- **Frontend**: Next.js 15 (App Router) with React, TypeScript, Tailwind CSS, and shadcn/ui components
- **Backend**: FastAPI (async) with route → service → repository architecture
- **Database**: PostgreSQL (Neon) accessed via SQLAlchemy 2.0 async ORM
- **Authentication**: Clerk (JWT verification)
- **Migrations**: Alembic
- **AI**: Google Gemini via google-genai SDK

## High-Level Flow

```text
Browser
   ↓
Next.js / React (Server Components + Client Components)
   ↓
FastAPI REST API (Bearer token from Clerk)
   ↓
Service Layer (business/domain logic)
   ↓
Repository Layer (data access)
   ↓
PostgreSQL (via SQLAlchemy async)
```

## Domain & Intelligence Flow

```text
Behavior
    ↓
Analytics ───────────────┐
    ↓                    │
Task Analysis ───────────┤
                         ▼
                  Pattern Detection
                         ↓
              verified facts served by the API
```

Deterministic engines run without any AI. Gemini is invoked only when the user
explicitly asks a question:

```text
User asks a question (Insights page, explicit send)
    ↓
AIContextBuilder (verified facts for the selected date)
    ↓
Gemini
    ↓
Chat response
```

## Context-Aware AI Chat

```text
User question
     ↓
ChatService
     ↓
AIContextBuilder
     ├── Analytics
     ├── Task Analysis
     └── Pattern Detection
     ↓
Verified context
     ↓
Gemini
     ↓
AI response
```

- Route: `POST /api/insights/chat` (`app/api/routes/insights.py`), user taken from authentication only
- User-triggered only: opening the Insights page (or changing its date) sends no AI request; Gemini runs after an explicit send
- `AIContextBuilder` (`app/services/ai_context_builder.py`) assembles a validated `ChatContext` for the selected date from the existing engines — no calculations of its own, no ORM/repository objects
- `ChatService` (`app/services/ai_chat_service.py`) renders the context into a structured prompt with the recent conversation and sends it through the `AIProvider` abstraction
- `GeminiProvider` (`app/services/ai_provider.py`) is the only Gemini-aware class; failures become a friendly 503 without leaking internals
- Conversation history is kept client-side (no chat database) and truncated to the most recent messages

## Responsibility Breakdown

### Frontend (Next.js/React)
- Server-side data fetching via `server-only` functions in `apps/web/src/lib/backend.ts`
- Server actions for mutations (`apps/web/src/app/actions.ts`)
- Day-wise date navigation through the URL (`?date=YYYY-MM-DD`) on Behaviors, Tasks, Analytics, Patterns and Insights; a shared `DateNavigator` renders the control
- UI components using shadcn/ui (dark theme by default)
- Navigation: Today, Tasks, Analytics, Patterns, Insights
- Authentication via Clerk

### Backend (FastAPI)
- REST API routes under `app/api/routes/`
- JWT auth middleware via Clerk token validation (`app/core/auth.py`)
- Request validation with Pydantic models
- Dependency injection in `app/api/dependencies.py`
- CORS/origin handling via config
- Structured error responses (`app/core/errors.py`)

### Services
- Encapsulate business rules and invariants
- Orchestrate repositories
- Never access DB directly; go through repositories
- Examples: `BehaviorService`, `TaskService`, `AnalyticsService`, `PatternDetectionService`, `TaskAnalysisService`, `AIInsightService`, `AIContextBuilder`, `ChatService`

### Repositories
- Interface + implementation pattern (`repositories/interfaces/` and implementations)
- Encapsulate SQLAlchemy queries
- Return domain models (SQLAlchemy ORM models)
- User scoping enforced at query level

### Persistence
- SQLAlchemy 2.0 async (`app/db/session.py`)
- Alembic migrations (`alembic/versions/`)
- Models in `app/models/`
- Junction tables for many-to-many (context tags)

## Authentication & Authorization

- Frontend obtains Clerk session token; sends as `Authorization: Bearer <token>`
- Backend validates token via `pyjwt` against Clerk JWKS (`app/core/auth.py`)
- Extracts `clerk_user_id`, looks up local `User` record (`app/services/user_service.py`)
- All operations scoped to `user_id` (user isolation enforced)
- Webhooks sync Clerk users to local DB (`app/api/routes/webhooks.py`)

## Analytics & Intelligence

- **Analytics**: Deterministic aggregation of behaviors and tasks into daily summaries (tracked vs unaccounted, categories, activities)
- **Task Analysis**: Matches behaviors to tasks by time overlap and category/activity/context alignment; computes effective minutes and completion rate
- **Pattern Detection**: Detects transitions (category/activity) across contiguous chains (no bridging of gaps), computes conditional probabilities, finds context associations by averaging durations with minimum sample thresholds
- **AI Insight Engine**: Consumes only verified facts from the above engines; builds structured context; calls Gemini (backend-only) with strict prompt rules; validates structured response; fails gracefully without breaking UI. `GET /insights/daily` stays available as an on-demand endpoint but the frontend never calls it automatically
- **AI Chat Engine**: The primary AI experience — a user-triggered chatbot on the Insights page; `AIContextBuilder` injects daily analytics, task analysis, and patterns for the selected date, the recent conversation is appended, and Gemini answers under the same no-fabrication rules (see `docs/engines/ai-chat-engine.md`)

## Security

- No secrets sent to frontend (API keys never exposed)
- Gemini API key loaded only from backend env
- User isolation enforced in all queries
- All DB access async; transactions managed by session
- Soft deletes where applicable (behaviors)
- No raw DB dumps to AI

## Environment

- Backend config via `pydantic-settings` (`app/core/config.py`)
- Required: `DATABASE_URL`, `CLERK_WEBHOOK_SECRET`, `CLERK_ISSUER` (optional `CLERK_AUDIENCE`, `CLERK_ALLOWED_ORIGINS`)
- AI: `GEMINI_API_KEY`, `GEMINI_MODEL` (optional; defaults handled in service)
