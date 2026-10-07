# AI Chat Engine

## 1. Purpose

A context-aware conversational interface inside the Insights page. The user asks
questions in plain language ("Why was my study completion low yesterday?") and the
backend answers from the user's own recorded data.

Gemini is never called on page load. The request happens only after the user
explicitly sends a message, and the selected date is passed with that message.

The chatbot does not discover facts on its own. Every number, task, and pattern in
the answer is computed by the existing deterministic engines and injected into the
prompt before Gemini is called. Gemini only interprets, explains, reasons, and
keeps the conversation going.

Explicitly out of scope: LangChain, LangGraph, RAG, vector databases, embeddings,
agents, Redis, background workers, web search, persistent chat storage.

## 2. Chat request flow

```text
POST /api/insights/chat           (thin route: app/api/routes/insights.py)
       ↓
ChatService                       (app/services/ai_chat_service.py)
       ↓
Authenticate current user         (CurrentUser dependency → user.id from Clerk token)
       ↓
AIContextBuilder                  (app/services/ai_context_builder.py)
       ├── AnalyticsService
       ├── TaskAnalysisService
       ├── PatternDetectionService
       └── TaskRepository (titles only)
       ↓
Verified ChatContext (Pydantic)
       ↓
build_chat_prompt(context, history, message)
       ↓
AIProvider.complete(system_prompt, prompt)   (app/services/ai_provider.py)
       ↓
GeminiProvider → google-genai (async)
       ↓
ChatResponse { reply, date }
```

Contract:

```json
// request
{
  "message": "Why was my study completion low yesterday?",
  "date": "2026-10-05",
  "tz_offset_minutes": 330,
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

// response 200
{ "reply": "Your planned study time was ...", "date": "2026-10-05" }

// response 503 (Gemini failed)
{ "error": { "code": "chat_unavailable",
             "message": "I couldn't generate a response right now. Your recorded data is still available." } }
```

The user id is never accepted from the frontend. It always comes from the
authenticated Clerk token via the existing `CurrentUser` dependency.

## 3. Automatic context injection

Every request builds a fresh context for one authenticated user and one period:

- selected date (from the request; defaults to the server's current date)
- daily analytics for that date
- tasks scheduled for that date plus their task analysis
- patterns detected for that date

Nothing else is injected. The whole database is never dumped into a prompt, and
no other user's data can enter the context because every repository call is
scoped by the authenticated `user_id`.

## 4. Context Builder

`AIContextBuilder.build(session, user_id, day, tz_offset_minutes)` returns a
`ChatContext` (Pydantic, `app/schemas/ai_chat.py`):

```text
ChatContext
├── period      → {start, end} of the selected day
├── analytics   → day_minutes, tracked_minutes, unaccounted_minutes,
│                 behavior_count, categories[], activities[], task_totals
├── tasks[]     → title, category, activity_label, planned_minutes,
│                 effective_minutes, completion_rate
└── patterns[]  → category_transition | activity_transition | context_association
```

Rules:

- The builder performs no statistics itself; it only assembles engine output.
- No SQLAlchemy model, repository object, or internal id ever enters the
  structure — only display-ready values (titles, labels, minutes, rates).
- Task titles come from `TaskRepository.get_tasks_for_date` and are joined to
  `TaskAnalysisService.analyze_tasks_for_date` results by `task_id`; the
  completion calculation is never duplicated.

`render_chat_context(context)` converts the structure into deterministic,
readable text — the same context always produces the same text.

## 5. How the deterministic engines contribute

| Engine | Contributes |
| --- | --- |
| `AnalyticsService.daily` | tracked/unaccounted minutes, behavior count, category totals, activity totals, task totals |
| `TaskAnalysisService` | per-task planned vs effective minutes and completion rate (existing overlap/match-score calculation, reused unchanged) |
| `PatternDetectionService.transitions` | category and activity transition counts with probabilities (min. count threshold, default 5) |
| `PatternDetectionService.context` | context associations: average session duration per dimension/context with sample sizes (min. sessions threshold, default 3) |
| `TaskRepository` | task titles/labels for the selected date (presentation only) |

Example rendered context:

```text
<life_tracker_context>
Period: October 5, 2026

Analytics:
- Day length: 1440 minutes
- Tracked: 450 minutes
- Unaccounted: 990 minutes (unknown time; never assume what it contains)
- Behaviors recorded: 6
- Categories: Study 240 min; Entertainment 90 min
- Activities: Study/DSA 180 min
- Task totals: 1 task(s), planned 180 min, effective 120 min, completion 66.67%

Tasks:
- "DSA Preparation" [Study/DSA]: planned 180 min, effective 120 min, completion 66.67%

Patterns (deterministic detections for this period; patterns below minimum sample thresholds are not reported):
- context_association: Study/CN, dimension=environment: Library 96 min average over 8 session(s) vs Home 48 min average over 7 session(s) (difference 48 min)
</life_tracker_context>
```

If a section is empty it says so explicitly (`none recorded`,
`(no tasks scheduled for this date)`, `(no patterns detected for this date)`)
instead of hiding the gap.

## 6. Gemini interaction

- `AIProvider` is a one-method protocol (`complete(system_prompt, prompt)`).
- `GeminiProvider` is the only Gemini-aware class; `ChatService` never imports
  the SDK.
- Uses the async client (`client.aio.models.generate_content`) with
  `system_instruction` = the chat system prompt, `temperature = 0.4`,
  a 45-second `asyncio.wait_for` timeout, and the model from `GEMINI_MODEL`
  (default `gemini-2.5-flash`).
- Streaming was not adopted: the app's other AI endpoint
  (`/insights/daily`, on-demand and no longer called by the UI) is plain
  request/response, and reliability was preferred
  over adding a streaming path for one feature.
- The API key stays in backend env (`GEMINI_API_KEY`) and is passed straight to
  the SDK; it is never serialized into a response.

## 7. Conversation history

- The frontend keeps the conversation in React state; there is no persistent
  chat database.
- Each request sends the current conversation as `history` (capped at 20
  messages by request validation).
- The service sends only the most recent 10 messages to Gemini, so prompts stay
  small no longer the conversation grows.
- Changing the selected date resets the conversation in the UI.

## 8. Prompt structure

System prompt (`CHAT_SYSTEM_PROMPT`): identity ("You are the Life Tracker AI
assistant"), data rule, no-fabrication rule, unaccounted-time rule, causality
rule, period scope, coaching-as-experiments, conversation/tone rules.

User message layout:

```text
<life_tracker_context>
...verified facts...
</life_tracker_context>

<conversation>
user: ...
assistant: ...
</conversation>

<user_question>
Why was my study completion low?
</user_question>
```

## 9. Hallucination / unsupported-claim prevention

- Facts are established *before* the model sees them; the model receives no raw
  data access, so it can only restate/interpret what is in the context.
- The system prompt forbids claims not supported by the context and requires
  saying "the context does not contain that" otherwise.
- Unaccounted time must be treated as unknown — never as rest, sleep, phone
  usage, or distraction.
- Observational language only: "your recorded CN sessions have been longer in
  the library", never "the library makes you study better".
- Period scope: asked about a week/month, the model must state that only the
  selected day is available rather than inventing aggregates.
- Empty sections are explicit, so "no patterns" is reported as "no patterns",
  not filled in.

## 10. Error handling

| Failure | Handling |
| --- | --- |
| Missing/invalid bearer token | 401 `unauthenticated` (existing auth flow) |
| Missing `GEMINI_API_KEY` | `AIUnavailable` → 503 `chat_unavailable` |
| Gemini timeout (45s) | wrapped in `asyncio.wait_for` → 503 `chat_unavailable` |
| Rate limit / transport / SDK error | logged server-side only → 503 `chat_unavailable` |
| Empty or whitespace response | 503 `chat_unavailable` |
| Unexpected exception in the route | mapped to 503 `chat_unavailable` |

Every AI failure returns the same user-facing text:

```text
I couldn't generate a response right now. Your recorded data is still available.
```

No fallback answer is fabricated, and raw exception text (which could contain
SDK details or the key) is never returned to the client. Tests assert this.

## 11. Why the LLM does not query the database

An LLM writing and interpreting queries cannot be trusted to be correct, and
correctness here means the user's real numbers. Allowing model-driven queries
would make every answer a potential fabrication and would require exposing
schema/ids to the prompt. Instead the pipeline is closed: repositories are
called by deterministic services, results are validated into Pydantic models,
and the model receives only finished facts.

## 12. Why deterministic engines establish facts first

Calculations, aggregation, and pattern detection are code with tests — repeatable
and auditable. The generative layer's job is language, not arithmetic. Keeping
"truth" in the engines and "explanation" in Gemini gives one source of truth
shared with the Analytics/Patterns pages, so the chatbot and
the dashboards can never disagree about a number.

## 13. How to explain this in an interview (30–60 seconds)

"The chatbot is deliberately thin. When a question arrives, the backend first
authenticates the user, then an AIContextBuilder pulls that user's day from the
same deterministic engines the rest of the app uses — analytics, task analysis,
and pattern detection — and validates everything into a Pydantic context. That
context is rendered into a structured prompt with the recent conversation and
the question, and only then does Gemini see it. The model is instructed to use
nothing but the provided facts, to treat unaccounted time as unknown, and to
avoid causal claims. So the engines decide what is true and the model decides
how to explain it. If Gemini fails or the key is missing, the user gets a
friendly error instead of a made-up answer, and their data pages are unaffected."

## Test coverage

`tests/test_ai_chat.py` (Gemini is mocked via a fake `AIProvider`):

- chat requires authentication (401 without a token)
- context is scoped to the authenticated user (another user's data never appears)
- analytics and task analysis appear in the prompt (completion rate from the engine)
- detected patterns appear in the prompt
- history is passed through and truncated to the recent window
- an empty day produces explicit "nothing recorded" context, not invented facts
- provider failure → 503 friendly error with no internal details
- invalid (empty) provider response → 503 friendly error
- API key material never reaches the client
- empty message is rejected (422)
