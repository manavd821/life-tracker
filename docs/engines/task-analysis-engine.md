# Task Analysis Engine

## Purpose
Quantifies how effectively recorded behaviors align with planned tasks (planned vs actual/effective time). Provides matching based on time overlap, category/activity alignment, and shared context tags.

## Input
- Task(s) (with planned_minutes, primary_category, optional activity_label, context_tags, time window)
- Behaviors overlapping the task window (from BehaviorRepository)
- User ID

## Output
- Per-task `TaskAnalysis` / `TaskAnalysisDetail` with effective_minutes, completion_rate, contributions
- Aggregated `TaskAnalysisTotals` (count, planned, effective, completion rate)

## Responsibilities
- Find behaviors overlapping task(s) (temporal intersection)
- Score match: exact activity match > category-only; bonus for shared context tags
- Compute overlap minutes and effective_minutes = overlap_minutes * match_score
- Calculate completion_rate = effective / planned * 100 (0 if planned <= 0)
- Batch analysis across date ranges and user tasks
- Enforce user ownership of tasks

## What does NOT belong to it
- Raw behavior aggregation beyond overlap
- Pattern detection/transitions
- AI interpretation
- Creating behaviors/tasks (delegates to services)

## Data Flow
```text
Route (tasks.py / analytics)
  ↓
TaskAnalysisService
  ↓
TaskRepository (tasks) + BehaviorRepository (overlapping behaviors)
  ↓
DB
```

## Business Rules (actual implementation)
- **Temporal matching**: Overlap if `behavior.start_time < task.end_time and behavior.end_time > task.start_time` (half-open logic for intervals)
- **Match scoring**: `EXACT_ACTIVITY_SCORE=1.0`, `CATEGORY_ONLY_SCORE=0.5`, `CONTEXT_BONUS=0.25`, `MAX_SCORE=1.0`. If categories differ → score 0
- **Context bonus**: Add bonus if any behavior context tag id is in task’s context tag set; score capped at MAX_SCORE
- **Effective minutes**: `round(overlap_minutes * score, 2)` per contributing behavior
- **Completion rate**: `(effective / planned) * 100`, rounded to 2 decimals; 0 if planned <= 0
- **Batch optimization**: For multiple tasks, fetch behaviors once for the combined window [min start, max end]
- **Contributions**: Each behavior contributing score>0 included with match details and matched context tags

## Example
Task: Study/CN 09:00–11:00 (planned 120). Behavior Study/CN 09:00–10:30 overlapping fully with exact match (1.0) → effective 90. If behavior lacks activity but same category → 45. If shares context tag → bonus up to 1.0.

## How to explain this in an interview
“Task Analysis measures alignment by intersecting behaviors with task windows and scoring matches: exact activity gives full credit, category-only partial, shared context tags add bonus. Effective time is weighted overlap; completion rate is deterministic from these figures.”

## Important Design Decisions
- Deterministic scoring rules (no ML) keep “truth” objective
- Batch windowing minimizes queries
- Contributions preserved for transparency
- Ownership checks prevent cross-user analysis
- Rounds to 2 decimals for stable reporting
