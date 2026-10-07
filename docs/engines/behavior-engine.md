# Behavior Engine

## Purpose
The Behavior domain represents observed user activity over time. It tracks when activities start/end, their category, optional activity label, context tags, and subjective states. It enforces time invariants and user ownership.

## Input
- Create/Update behavior payloads (start_time, end_time, primary_category, activity_label_id, context_tag_ids, environment, energy_level, focus_state, emotion_state, notes, precision, source)
- Queries by date range / timeline window (with tz offset)
- User ID (from auth context)

## Output
- Behavior model instances (ORM) / API responses (BehaviorResponse)
- Timeline view: behaviors + computed unaccounted intervals + totals
- Validation errors (overlap, invalid times, invalid references)

## Responsibilities
- Validate non-overlapping behaviors for the same user (service-level invariant)
- Enforce start < end (or equivalent validation)
- Compute duration (derived, not trusted from client)
- Manage activity labels and context tag associations
- Soft delete behaviors (deleted_at set)
- Scope all queries to user_id
- Return timeline with unaccounted time computed from gaps

## What does NOT belong to it
- Analytics aggregations (handled by Analytics Engine)
- Task matching/effective time (Task Analysis)
- Pattern detection (transitions/associations)
- AI insights/coaching

## Data Flow
```text
Route (behaviors.py)
  ↓
BehaviorService (validation, overlap checks, associations)
  ↓
BehaviorRepository (CRUD + range queries + timeline assembly)
  ↓
SQLAlchemy models (Behavior, ActivityLabel, ContextTag, maps)
  ↓
PostgreSQL
```

## Business Rules (actual implementation)
- **No-overlap invariant**: For a given user, behaviors must not overlap in time (service checks against existing active behaviors in range)
- **Duration calculation**: `duration_minutes = (end_time - start_time).total_seconds() // 60` (computed server-side; client duration not used)
- **User ownership**: All mutations/reads require user_id; cross-user access prevented
- **Activity/category consistency**: Activity labels must belong to user and match primary_category if validated (service checks)
- **Context tags**: Validated for user and category; associations managed via junction table
- **Unaccounted time**: Computed as gaps between consecutive behaviors in sorted timeline (not stored as Behavior)
- **Soft deletion**: `delete` sets `deleted_at` timestamp; repository filters out deleted behaviors
- **Time ordering**: Behaviors returned sorted by start_time; timeline normalization respects continuity
- **Precision/source**: Stored as enums/strings per schema

## Example (realistic)
Timeline for a day: 09:00–10:00 Study (CN), 10:00–12:00 Work → tracked 180m, unaccounted is whatever gaps remain in the day window. Overlap attempt (e.g. 09:30–10:30) rejected.

## How to explain this in an interview
“The Behavior engine models discrete activities with time ranges. The service enforces non-overlapping, user-scoped invariants and derives duration. Unaccounted time is computed from timeline gaps rather than persisted, keeping the source of truth as observed behaviors.”

## Important Design Decisions
- Overlap validation lives in service (not DB constraint alone) to give clear domain errors and enforce business invariant
- Duration derived server-side to prevent trust boundary issues
- Soft delete preserves history without losing referential integrity for task analysis
- Unaccounted time not a Behavior entity (avoids conflating “missing data” with “activity”)
- Repositories return ORM models; schemas handle API shaping
- Junction tables for context tags keep many-to-many normalized
