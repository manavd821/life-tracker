# Pattern Detection Engine

## Purpose
Deterministically detects patterns in recorded behaviors: category/activity transitions with conditional probabilities and context associations (duration differences by context). No inference, bridging, or coaching.

## Input
- User ID, date range (start/end), tz offset
- BehaviorRepository (behaviors for range, context duration totals)
- Config: `min_transition_count`, `min_context_sessions`

## Output
- `TransitionPatterns`: window, minimum threshold, category_transitions[], activity_transitions[]
- `ContextPatterns`: window, minimum threshold, context_stats[], associations[]

## Responsibilities
- Resolve date window with validation (end >= start)
- Split behaviors into contiguous chains (no bridging across gaps)
- Detect transitions within chains only
- Compute conditional probabilities (P(to | from))
- Find context associations where same activity differs across contexts (longest/shortest avg)
- Apply minimum thresholds before surfacing

## What does NOT belong to it
- Causal explanations (AI’s job)
- Recommendations/coaching
- Task analysis/analytics beyond reading behaviors

## Data Flow
```text
Route (patterns.py)
  ↓
PatternDetectionService.transitions/context
  ↓
BehaviorRepository.list_for_range / get_context_duration_totals
  ↓
DB
```

## Business Rules (actual implementation)

### Windowing
- Defaults: start = today or provided, end = start if None; rejects inverted range
- Uses `range_window(start,end,tz_offset)`

### Contiguous chains
- Behaviors sorted by (start_time, behavior_id)
- Chain continues if current[-1].end_time == behavior.start_time; else close chain and start new
- Gaps (end != next.start) break chains → transitions never counted across gap (no bridging)

### Transitions
- **Category sequence**: collapse consecutive same-category behaviors (Study/DSA→Study/CN yields single Study step) so Study→Study never produced
- **Category transitions**: pairs (from_category, to_category) counted within chain
- **Activity transitions**: track previous (category, activity_label) only when behavior has activity label; missing label breaks activity chain (no invented name); only counted when changes to different labeled activity
- **Probabilities**: conditional P(to|from) = count / total_transitions_from_source (rounded to 4 decimals); per-source sums to ~1.0 where multiple targets meet threshold
- **Threshold**: include only if count >= min_transition_count (default 5; >=1 enforced)

### Context
- `get_context_duration_totals` returns per (category, activity_label, dimension, context): session_count, total_duration_minutes
- `context_stat`: average = total/session_count (rounded to 2 decimals) if sessions>0
- **Associations**: group by (dimension, category, activity_label_or_empty). Require >=2 different contexts and each session_count >= min_context_sessions (default 3). Find longest and shortest by average; only report if longest > shortest. Compute difference_minutes and ratio (longest/shortest). Sorted by (-difference, dimension, activity_label)

### Isolation & Filters
- All scoped to user_id; soft-deleted excluded
- Only observed data reported

## Example
5 consecutive Study→Entertainment days → category count 5, prob 1.0. CN in Library avg 96m (8 sess), Home 48m (7) → association Library>Home +48m. Gap (10:00–11:00 unaccounted) between Study and Entertainment produces no transition.

## How to explain this in an interview
“Pattern Detection is purely statistical over contiguous behavior chains: gaps break continuity (no bridging), consecutive same-category steps are collapsed, activity transitions require labeled behaviors (no invented names). Probabilities are conditional on source. Context associations compare observed averages across contexts only when sample sizes meet threshold—correlation reported, causation never assumed.”

## Important Design Decisions
- Chain-based detection enforces “contiguous reality” (unaccounted gap = uncertainty)
- Collapse same-category prevents spurious self-transitions
- Activity chain breaks on unlabeled (preserves data integrity)
- Thresholds prevent surfacing noise
- Associations report both ends + samples + difference/ratio for transparency
- Deterministic, no external calls
