from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def day_window(day: date, tz_offset_minutes: int = 0) -> tuple[datetime, datetime]:
    tz = timezone(timedelta(minutes=tz_offset_minutes))
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def range_window(
    start_day: date, end_day: date, tz_offset_minutes: int = 0
) -> tuple[datetime, datetime]:
    start, _ = day_window(start_day, tz_offset_minutes)
    _, end = day_window(end_day, tz_offset_minutes)
    return start, end


def window_minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)