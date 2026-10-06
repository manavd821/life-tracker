from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.enums import PrimaryCategory
from app.repositories.activity_label_repository import ActivityLabelRepository
from app.repositories.context_tag_repository import ContextTagRepository
from app.schemas.behavior import CreateBehavior
from app.schemas.task import CreateTask

TZ = timezone.utc
DAY = date(2026, 10, 4)


def at(hour: int, minute: int = 0, day: int = 4) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


async def record(
    session,
    behavior_service,
    user_id,
    start,
    end,
    label_id=None,
    category=PrimaryCategory.Study,
):
    return await behavior_service.create(
        session,
        user_id,
        CreateBehavior(
            start_time=start,
            end_time=end,
            primary_category=category,
            activity_label_id=label_id,
        ),
    )


async def plan(session, task_service, user_id, start, end, label_id=None, title="Task", category=PrimaryCategory.Study):
    return await task_service.create(
        session,
        user_id,
        CreateTask(
            title=title,
            start_time=start,
            end_time=end,
            primary_category=category,
            activity_label_id=label_id,
        ),
    )


# ---------- summary ----------


@pytest.mark.asyncio
async def test_empty_day(session, user, analytics_service):
    result = await analytics_service.daily(session, user, DAY)
    assert result.date == "2026-10-04"
    assert result.summary.day_minutes == 1440
    assert result.summary.tracked_minutes == 0
    assert result.summary.unaccounted_minutes == 1440
    assert result.summary.behavior_count == 0
    assert result.categories == []
    assert result.activities == []
    assert result.tasks.count == 0
    assert result.tasks.completion_rate == 0.0


@pytest.mark.asyncio
async def test_tracked_minutes_and_count(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(9), at(10))
    await record(session, behavior_service, user, at(11), at(12, 30))
    await record(session, behavior_service, user, at(14), at(15))

    result = await analytics_service.daily(session, user, DAY)
    assert result.summary.tracked_minutes == 60 + 90 + 60
    assert result.summary.behavior_count == 3
    assert result.summary.unaccounted_minutes == 1440 - 210


@pytest.mark.asyncio
async def test_unaccounted_never_counts_rest_as_unaccounted(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(23), at(23, 59), category=PrimaryCategory.Rest)

    result = await analytics_service.daily(session, user, DAY)
    rest = next(c for c in result.categories if c.category == PrimaryCategory.Rest)
    assert rest.duration_minutes == 59
    assert result.summary.tracked_minutes == 59
    assert result.summary.unaccounted_minutes == 1440 - 59


@pytest.mark.asyncio
async def test_soft_deleted_behaviors_are_excluded(session, user, behavior_service, analytics_service):
    created = await record(session, behavior_service, user, at(9), at(10))
    await behavior_service.delete(session, user, created.behavior_id)

    result = await analytics_service.daily(session, user, DAY)
    assert result.summary.tracked_minutes == 0
    assert result.summary.behavior_count == 0
    assert result.categories == []


# ---------- categories ----------


@pytest.mark.asyncio
async def test_category_aggregation(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(9), at(13), category=PrimaryCategory.Study)
    await record(session, behavior_service, user, at(14), at(16), category=PrimaryCategory.Work)
    await record(session, behavior_service, user, at(17), at(18, 30), category=PrimaryCategory.Entertainment)
    await record(session, behavior_service, user, at(19), at(19, 45), category=PrimaryCategory.Health)

    result = await analytics_service.daily(session, user, DAY)
    totals = {c.category: c.duration_minutes for c in result.categories}
    assert totals == {
        PrimaryCategory.Study: 240,
        PrimaryCategory.Work: 120,
        PrimaryCategory.Entertainment: 90,
        PrimaryCategory.Health: 45,
    }
    assert result.summary.tracked_minutes == sum(totals.values())


@pytest.mark.asyncio
async def test_categories_sorted_by_duration_descending(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(9), at(10), category=PrimaryCategory.Health)
    await record(session, behavior_service, user, at(11), at(15), category=PrimaryCategory.Study)

    result = await analytics_service.daily(session, user, DAY)
    assert [c.category for c in result.categories] == [
        PrimaryCategory.Study,
        PrimaryCategory.Health,
    ]


# ---------- activities ----------


@pytest.mark.asyncio
async def test_activity_aggregation_groups_by_category_and_label(session, user, behavior_service, analytics_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    cn = await labels.add(session, user, "Study", "CN")
    youtube = await labels.add(session, user, "Entertainment", "YouTube")

    await record(session, behavior_service, user, at(9), at(10), cn.activity_label_id)
    await record(session, behavior_service, user, at(10), at(11), dsa.activity_label_id)
    await record(
        session,
        behavior_service,
        user,
        at(14),
        at(15),
        youtube.activity_label_id,
        category=PrimaryCategory.Entertainment,
    )

    result = await analytics_service.daily(session, user, DAY)
    rows = {(a.category, a.activity_label): a.duration_minutes for a in result.activities}
    assert rows[(PrimaryCategory.Study, "DSA")] == 60
    assert rows[(PrimaryCategory.Study, "CN")] == 60
    assert rows[(PrimaryCategory.Entertainment, "YouTube")] == 60


@pytest.mark.asyncio
async def test_behaviors_without_label_report_null_not_a_placeholder(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(9), at(10))

    result = await analytics_service.daily(session, user, DAY)
    assert len(result.activities) == 1
    assert result.activities[0].activity_label is None
    assert result.activities[0].category == PrimaryCategory.Study
    assert result.activities[0].duration_minutes == 60


@pytest.mark.asyncio
async def test_activity_totals_sum_to_category_totals(session, user, behavior_service, analytics_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    await record(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)
    await record(session, behavior_service, user, at(11), at(12))

    result = await analytics_service.daily(session, user, DAY)
    assert sum(a.duration_minutes for a in result.activities) == result.summary.tracked_minutes
    assert sum(c.duration_minutes for c in result.categories) == result.summary.tracked_minutes


# ---------- tasks ----------


@pytest.mark.asyncio
async def test_task_aggregates(session, user, task_service, behavior_service, analytics_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    os_ = await labels.add(session, user, "Study", "OS")

    await plan(session, task_service, user, at(9), at(12), dsa.activity_label_id, "DSA")
    await plan(session, task_service, user, at(14), at(15), title="CN")

    await record(session, behavior_service, user, at(9), at(10), os_.activity_label_id)
    await record(session, behavior_service, user, at(10), at(11), dsa.activity_label_id)

    result = await analytics_service.daily(session, user, DAY)
    assert result.tasks.count == 2
    assert result.tasks.planned_minutes == 180 + 60
    # DSA task: 09:00-10:00 OS scores 0.5 (30) and 10:00-11:00 DSA scores 1.0 (60)
    assert result.tasks.effective_minutes == 90.0
    assert result.tasks.completion_rate == 37.5


@pytest.mark.asyncio
async def test_task_completion_is_weighted_not_averaged(session, user, task_service, behavior_service, analytics_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")

    await plan(session, task_service, user, at(9), at(10), dsa.activity_label_id, "A")
    await plan(session, task_service, user, at(14), at(23), dsa.activity_label_id, "B")
    await record(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)

    result = await analytics_service.daily(session, user, DAY)
    # 60 of 600 minutes, not the mean of 100% and 0% which would be 50%
    assert result.tasks.planned_minutes == 600
    assert result.tasks.effective_minutes == 60.0
    assert result.tasks.completion_rate == 10.0


@pytest.mark.asyncio
async def test_planned_tasks_with_no_behaviors_report_zero_completion(session, user, task_service, analytics_service):
    await plan(session, task_service, user, at(14), at(15), title="Read CN")

    result = await analytics_service.daily(session, user, DAY)
    assert result.tasks.count == 1
    assert result.tasks.planned_minutes == 60
    assert result.tasks.effective_minutes == 0.0
    assert result.tasks.completion_rate == 0.0


@pytest.mark.asyncio
async def test_tasks_on_other_days_are_excluded(session, user, task_service, behavior_service, analytics_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    today = await plan(session, task_service, user, at(9), at(12), dsa.activity_label_id, "Today")
    await plan(
        session, task_service, user, at(9, day=5), at(12, day=5), dsa.activity_label_id, "Tomorrow"
    )
    await record(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)

    result = await analytics_service.daily(session, user, DAY)
    assert result.tasks.count == 1
    assert result.tasks.planned_minutes == 180

    tomorrow = await analytics_service.daily(session, user, date(2026, 10, 5))
    assert tomorrow.tasks.count == 1
    assert tomorrow.tasks.planned_minutes == 180
    assert tomorrow.tasks.effective_minutes == 0.0


# ---------- date filtering ----------


@pytest.mark.asyncio
async def test_behaviors_from_another_day_are_excluded(session, user, behavior_service, analytics_service):
    await record(session, behavior_service, user, at(9), at(10))
    await record(session, behavior_service, user, at(9, day=5), at(10, day=5))

    result = await analytics_service.daily(session, user, DAY)
    assert result.summary.behavior_count == 1
    assert result.summary.tracked_minutes == 60


@pytest.mark.asyncio
async def test_behavior_spanning_outside_the_day_is_clipped_to_the_day(session, user, behavior_service, analytics_service):
    # 23:00 on day 3 through 01:00 on day 4: only 60 minutes fall inside day 4
    await record(session, behavior_service, user, datetime(2026, 10, 3, 23, 0, tzinfo=TZ), datetime(2026, 10, 4, 1, 0, tzinfo=TZ))

    result = await analytics_service.daily(session, user, DAY)
    assert result.summary.tracked_minutes == 60
    assert result.summary.behavior_count == 1
    assert result.summary.unaccounted_minutes == 1440 - 60
    assert result.categories[0].duration_minutes == 60

    previous = await analytics_service.daily(session, user, date(2026, 10, 3))
    assert previous.summary.tracked_minutes == 60
    assert previous.summary.behavior_count == 1


@pytest.mark.asyncio
async def test_tz_offset_shifts_the_day_window(session, user, behavior_service, analytics_service):
    # 23:30 UTC is 09:30 the next day at +600 minutes
    await record(session, behavior_service, user, at(23, 30, day=4), at(23, 59, day=4))

    utc_day = await analytics_service.daily(session, user, DAY)
    shifted = await analytics_service.daily(session, user, date(2026, 10, 5), tz_offset_minutes=600)

    assert utc_day.summary.tracked_minutes == 29
    assert shifted.summary.tracked_minutes == 29


# ---------- isolation ----------


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_analytics(session, user, other_user, behavior_service, task_service, analytics_service):
    labels = ActivityLabelRepository()
    tags = ContextTagRepository()
    my_label = await labels.add(session, user, "Study", "Mine")
    await labels.add(session, other_user, "Study", "Theirs")

    await record(session, behavior_service, user, at(9), at(10), my_label.activity_label_id)
    await record(session, behavior_service, other_user, at(9), at(13))
    await plan(session, task_service, other_user, at(9), at(12))

    result = await analytics_service.daily(session, user, DAY)
    assert result.summary.behavior_count == 1
    assert result.summary.tracked_minutes == 60
    assert result.categories == [
        type(result.categories[0])(category=PrimaryCategory.Study, duration_minutes=60)
    ]
    assert result.tasks.count == 0

    theirs = await analytics_service.daily(session, other_user, DAY)
    assert theirs.summary.tracked_minutes == 240
    assert theirs.tasks.count == 1