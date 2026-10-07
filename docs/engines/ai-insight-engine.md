# AI Insight Engine

## Purpose
Converts verified facts from deterministic engines into understandable insights and actionable coaching. AI is not responsible for calculating truth—only for interpretation/coaching within strict constraints.

## Current usage
`GET /insights/daily` is not called by the frontend: opening the Insights page
performs no AI request, and the insight/coaching cards are no longer rendered
there. The endpoint remains available as an on-demand API; the chatbot is the
primary AI interaction. Both features share the same engines and the same
no-fabrication rules.

## Relationship to the AI Chat Engine
Both features share the same intelligence pipeline and the same engines:

- **AI Insight Engine** (`GET /insights/daily`): one-shot generation of insight/coaching cards for a date.
- **AI Chat Engine** (`POST /insights/chat`): context-aware conversation for the same date, with the same verified context plus recent history.

`AIInsightService` builds `AIContext` (behavior summary, task summary, patterns); the chat's `AIContextBuilder` builds `ChatContext` (analytics, per-task facts, patterns) from the same `AnalyticsService`, `TaskAnalysisService`, and `PatternDetectionService`. The chat layer additionally goes behind the `AIProvider` → `GeminiProvider` abstraction (`app/services/ai_provider.py`); see `docs/engines/ai-chat-engine.md`. Neither feature lets the model touch the database or recompute a statistic.

## Input
- Verified structured context built from Analytics + Task Analysis + Pattern Detection (never raw DB dumps)
- Gemini API key/model from env (backend-only)
- User ID, date range

## Output
- `AIResponse` with `insights[]` and `coaching[]` (each with titles/descriptions/reasoning/supporting_facts)
- Validated via Pydantic schemas

## Responsibilities
- Collect verified facts (behavior summary, task summary, transitions, context associations)
- Build minimal structured AI context (no IDs, no internal objects)
- Construct system prompt enforcing rules
- Call Gemini (google-genai) with JSON response schema
- Validate structured response; handle failures gracefully
- Never compute durations/probabilities/counts

## What does NOT belong to it
- Analytics/pattern calculations
- DB queries beyond what services return (uses existing services)
- Persistence/history (on-request generation per requirements)
- Exposing secrets to frontend

## Data Flow
```text
Route (insights.py GET /insights/daily?date=...)
  ↓
AIInsightService
  ↓
AnalyticsService + TaskAnalysisService + PatternDetectionService (reused)
  ↓
Build AIContext (structured facts)
  ↓
Gemini API (structured JSON)
  ↓
Pydantic validation → AIResponse
  ↓
Frontend
```

## Business Rules (prompt/implementation)
- **Do not invent facts**: Only use provided structured input
- **No unsupported causal claims**: Prefer observational language ("recorded sessions have been longer...")
- **Distinguish correlation/causation**: use "associated with", "observed more often", "appears", "recorded pattern"
- **Unaccounted time uncertainty**: never assume rest/entertainment/laziness/phone/sleeping unless explicit
- **Actionable coaching**: turn verified observations into practical experiments/suggestions
- **No judgment**: avoid shaming/moral language
- **Insight vs Coaching separation**: insights = "what does data show?"; coaching = "what could I try?"
- **Failure handling**: on timeout/invalid/malformed/error/missing key → return 503 with user-friendly message; dashboard unaffected
- **Backend-only**: Gemini never called from frontend; key never exposed

## Example Context (shape)
```json
{
  "period": {"start":"2026-10-04","end":"2026-10-04"},
  "behavior_summary": {"tracked_minutes":450,"unaccounted_minutes":990,"category_totals":[{"category":"Study","minutes":240}]},
  "task_summary": {"planned_minutes":300,"effective_minutes":210,"completion_rate":70},
  "patterns": [
    {"type":"context_association","category":"Study","activity_label":"CN","dimension":"environment","context_a":"Library","context_b":"Home","average_duration_a":96,"average_duration_b":48,"sample_a":8,"sample_b":7,"difference_minutes":48}
  ]
}
```

## Example Output
```json
{
  "insights": [{
    "title": "Longer CN sessions in the library",
    "description": "Your recorded CN sessions have been longer in the library than at home.",
    "supporting_facts": ["Library average: 96 minutes","Home average: 48 minutes","Library sessions: 8","Home sessions: 7"]
  }],
  "coaching": [{
    "title": "Experiment with library sessions",
    "recommendation": "Consider scheduling longer CN study blocks in the library.",
    "reasoning": "Your recorded sessions show an association between the library and longer CN sessions."
  }]
}
```

## How to explain this in an interview
“The AI Insight Engine treats deterministic analytics/patterns as ground truth: it builds a minimal structured context from existing services and asks Gemini to produce insights and coaching under strict rules (no fact invention, no causal claims, no judgment). Responses are schema-validated with Pydantic; if Gemini fails, the app degrades gracefully and still shows behavior/analytics data.”

## Important Design Decisions
- **Truth boundary**: AI never recomputes stats (enforced by design: input is precomputed facts)
- **Minimal context**: avoids leaking internal implementation (no DB IDs/repos)
- **Strict prompt**: codifies safety/architectural rules
- **Schema-first**: forces structured output, prevents freeform hallucination in shape
- **Backend isolation**: secrets stay server-side; frontend only consumes structured results
- **Fail-safe**: 503 with generic message, no fabricated fallback (prevents misleading user)
- **Configurable model/key** via env; no hardcoding
- **On-request (no persistence/queues)** appropriate for showcase scope
