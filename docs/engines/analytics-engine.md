# Analytics Engine

## Purpose
Aggregates behaviors and tasks into deterministic daily analytics (tracked vs unaccounted time, category/activity totals, task summary).

## Input
- Date `day` and timezone offset
- BehaviorRepository (day totals, category totals, activity totals)
- TaskAnalysisService (task analysis for date)

## Output
- `DailyAnalytics` with summary, categories, activities, tasks

## Responsibilities
- Compute day window from date + tz offset
- Get behavior_count and tracked_minutes for day
- Aggregate category totals and activity totals
- Summarize task analyses for the day
- Return structured, deterministic stats

## What does NOT belong to it
- Transitions/patterns (Pattern Detection)
- AI reasoning
- Cross-day trend modeling beyond what’s requested

## Data Flow
```text
Route (analytics.py)
  ↓
AnalyticsService.daily(day, tz_offset)
  ↓
BehaviorRepository.get_day_totals / get_category_totals / get_activity_totals
  + TaskAnalysisService.analyze_tasks_for_date
  ↓
DB
```

## Business Rules (actual implementation)
- Day window computed via `day_window(day, tz_offset_minutes)`; total day minutes = window length
- `unaccounted_minutes = day_minutes - tracked_minutes` (can be >= 0)
- Category totals: list of (category, duration_minutes)
- Activity totals: list of (category, activity_label, duration_minutes) (activity_label may be None)
- Tasks: aggregated via `TaskAnalysisService.summarize(analyses)` returning totals (count, planned, effective, completion rate)
- All queries scoped to user_id, exclude soft-deleted behaviors

## Example
Day with 1440 min window, tracked 450, unaccounted 990; Study 240m, CN (Study) 120m; tasks total planned 300, effective 210 (70%).

## How to explain this in an interview
“The Analytics Engine produces deterministic daily rollups: it sums behavior durations to get tracked time, computes unaccounted as the remainder of the day window, aggregates by category and activity, and incorporates task analysis totals—all without inference or estimation beyond arithmetic.”

## Important Design Decisions
- Unaccounted is derived (gap-based view of the day) not an entity
- Leverages TaskAnalysisService (no duplication of matching logic)
- Pure aggregations keep it objective and testable
- TZ-aware windows ensure correct day boundaries
