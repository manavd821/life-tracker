from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.errors import InvalidTimeRange, ResourceNotFound
from app.models.enums import PrimaryCategory
from app.repositories.activity_label_repository import ActivityLabelRepository
from app.repositories.context_tag_repository import ContextTagRepository
from app.schemas.behavior import CreateBehavior
from app.schemas.task import CreateTask, UpdateTask

TZ = timezone.utc


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 4, hour, minute, tzinfo=TZ)


async def make_label(session, user_id, category, name):
    return await ActivityLabelRepository().add(session, user_id, category.value, name)


async def make_tag(session, user_id, category, name):
    return await ContextTagRepository().add(session, user_id, category.value, name)


def task(start: datetime, end: datetime, **overrides) -> CreateTask:
    data = {
        "title": "DSA Preparation",
        "start_time": start,
        "end_time": end,
        "primary_category": PrimaryCategory.Study,
    }
    data.update(overrides)
    return CreateTask(**data)


async def behavior(
    session, behavior_service, user_id, start, end, label_id=None, tag_ids=None, category=PrimaryCategory.Study
):
    return await behavior_service.create(
        session,
        user_id,
        CreateBehavior(
            start_time=start,
            end_time=end,
            primary_category=category,
            activity_label_id=label_id,
            context_tag_ids=tag_ids or [],
        ),
    )


# ---------- creation and validation ----------


@pytest.mark.asyncio
async def test_create_task_derives_planned_minutes(session, user, task_service):
    response = await task_service.create(session, user, task(at(9), at(12)))
    assert response.planned_minutes == 180
    assert response.title == "DSA Preparation"


@pytest.mark.asyncio
async def test_task_rejects_start_after_end(session, user, task_service):
    with pytest.raises(InvalidTimeRange):
        await task_service.create(session, user, task(at(12), at(9)))


@pytest.mark.asyncio
async def test_tasks_may_overlap(session, user, task_service):
    first = await task_service.create(session, user, task(at(9), at(12), title="A"))
    second = await task_service.create(session, user, task(at(10), at(11), title="B"))
    assert first.task_id != second.task_id


@pytest.mark.asyncio
async def test_task_label_from_another_user_rejected(session, user, other_user, task_service):
    label = await make_label(session, other_user, PrimaryCategory.Study, "DSA")
    with pytest.raises(ResourceNotFound):
        await task_service.create(
            session, user, task(at(9), at(12), activity_label_id=label.activity_label_id)
        )


@pytest.mark.asyncio
async def test_task_label_wrong_category_rejected(session, user, task_service):
    label = await make_label(session, user, PrimaryCategory.Entertainment, "Gaming")
    with pytest.raises(InvalidTimeRange) as exc:
        await task_service.create(
            session, user, task(at(9), at(12), activity_label_id=label.activity_label_id)
        )
    assert exc.value.code == "activity_label_category_mismatch"


@pytest.mark.asyncio
async def test_task_tag_from_another_user_rejected(session, user, other_user, task_service):
    tag = await make_tag(session, other_user, PrimaryCategory.Study, "Notes")
    with pytest.raises(ResourceNotFound):
        await task_service.create(
            session, user, task(at(9), at(12), context_tag_ids=[tag.behavior_context_tag_id])
        )


@pytest.mark.asyncio
async def test_task_tag_wrong_category_rejected(session, user, task_service):
    tag = await make_tag(session, user, PrimaryCategory.Work, "Standup")
    with pytest.raises(InvalidTimeRange) as exc:
        await task_service.create(
            session, user, task(at(9), at(12), context_tag_ids=[tag.behavior_context_tag_id])
        )
    assert exc.value.code == "context_tag_category_mismatch"


@pytest.mark.asyncio
async def test_task_of_another_user_not_readable(session, user, other_user, task_service):
    created = await task_service.create(session, other_user, task(at(9), at(12)))
    with pytest.raises(ResourceNotFound):
        await task_service.get(session, user, created.task_id)


@pytest.mark.asyncio
async def test_update_and_delete_task(session, user, task_service):
    created = await task_service.create(session, user, task(at(9), at(12)))
    updated = await task_service.update(
        session, user, created.task_id, UpdateTask(title="CN reading", end_time=at(13))
    )
    assert updated.title == "CN reading"
    assert updated.planned_minutes == 240

    await task_service.delete(session, user, created.task_id)
    assert await task_service.list_for_day(session, user, None) == []


# ---------- analysis ----------


@pytest.mark.asyncio
async def test_analysis_matches_specification_example(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    os = await make_label(session, user, PrimaryCategory.Study, "OS")
    cn = await make_label(session, user, PrimaryCategory.Study, "CN")

    created = await task_service.create(
        session, user, task(at(9), at(12), activity_label_id=dsa.activity_label_id)
    )
    await behavior(session, behavior_service, user, at(9), at(10), os.activity_label_id)
    await behavior(session, behavior_service, user, at(10), at(11), dsa.activity_label_id)
    await behavior(session, behavior_service, user, at(11), at(12), cn.activity_label_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.planned_minutes == 180
    assert result.effective_minutes == 120
    assert result.completion_rate == 66.67
    assert [c.match_score for c in result.contributions] == [0.5, 1.0, 0.5]
    assert [c.effective_minutes for c in result.contributions] == [30.0, 60.0, 30.0]


@pytest.mark.asyncio
async def test_no_behaviors_gives_zero_completion(
    session, user, task_service, task_analysis_service
):
    created = await task_service.create(session, user, task(at(9), at(12)))
    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.effective_minutes == 0
    assert result.completion_rate == 0.0


@pytest.mark.asyncio
async def test_exact_match_with_context_tags_is_capped_at_one(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    tag = await make_tag(session, user, PrimaryCategory.Study, "Practice")

    created = await task_service.create(
        session,
        user,
        task(
            at(9),
            at(10),
            activity_label_id=dsa.activity_label_id,
            context_tag_ids=[tag.behavior_context_tag_id],
        ),
    )
    await behavior(
        session,
        behavior_service,
        user,
        at(9),
        at(10),
        dsa.activity_label_id,
        [tag.behavior_context_tag_id],
    )

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions[0].match_score == 1.0
    assert result.completion_rate == 100.0


@pytest.mark.asyncio
async def test_category_only_with_context_tags_scores_zero_point_seven_five(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    os = await make_label(session, user, PrimaryCategory.Study, "OS")
    tag = await make_tag(session, user, PrimaryCategory.Study, "Practice")

    created = await task_service.create(
        session,
        user,
        task(
            at(9),
            at(10),
            activity_label_id=dsa.activity_label_id,
            context_tag_ids=[tag.behavior_context_tag_id],
        ),
    )
    await behavior(
        session, behavior_service, user, at(9), at(10), os.activity_label_id,
        [tag.behavior_context_tag_id],
    )

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions[0].match_score == 0.75
    assert result.effective_minutes == 45.0
    assert result.completion_rate == 75.0


@pytest.mark.asyncio
async def test_task_without_activity_label_matches_any_activity_at_half(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(session, user, task(at(9), at(10)))
    await behavior(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions[0].match_score == 0.5


@pytest.mark.asyncio
async def test_different_category_never_contributes(
    session, user, task_service, behavior_service, task_analysis_service
):
    created = await task_service.create(session, user, task(at(9), at(10)))
    await behavior(
        session, behavior_service, user, at(9), at(10),
        category=PrimaryCategory.Work,
    )
    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions == []
    assert result.completion_rate == 0.0


@pytest.mark.asyncio
async def test_behavior_time_outside_task_window_is_clamped(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(10), at(12), activity_label_id=dsa.activity_label_id)
    )
    # spans 08:00-11:00 but only 10:00-11:00 falls inside the task
    await behavior(session, behavior_service, user, at(8), at(11), dsa.activity_label_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions[0].overlap_minutes == 60
    assert result.contributions[0].effective_minutes == 60.0
    assert result.completion_rate == 50.0


@pytest.mark.asyncio
async def test_behavior_fully_outside_window_does_not_contribute(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(14), at(15), activity_label_id=dsa.activity_label_id)
    )
    await behavior(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)
    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.contributions == []


@pytest.mark.asyncio
async def test_effective_time_never_exceeds_planned(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(9), at(12), activity_label_id=dsa.activity_label_id)
    )
    await behavior(session, behavior_service, user, at(9), at(12), dsa.activity_label_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.effective_minutes == 180
    assert result.completion_rate == 100.0


@pytest.mark.asyncio
async def test_deleted_behavior_stops_counting(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(9), at(10), activity_label_id=dsa.activity_label_id)
    )
    created_behavior = await behavior(
        session, behavior_service, user, at(9), at(10), dsa.activity_label_id
    )
    await behavior_service.delete(session, user, created_behavior.behavior_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.completion_rate == 0.0


@pytest.mark.asyncio
async def test_other_users_behaviors_do_not_contribute(
    session, user, other_user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, other_user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(session, user, task(at(9), at(10)))
    await behavior(session, behavior_service, other_user, at(9), at(10), dsa.activity_label_id)

    result = await task_analysis_service.analyze(session, user, created.task_id)
    assert result.completion_rate == 0.0


@pytest.mark.asyncio
async def test_analysis_updates_when_behavior_changes(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(9), at(12), activity_label_id=dsa.activity_label_id)
    )
    assert (await task_analysis_service.analyze(session, user, created.task_id)).completion_rate == 0.0

    await behavior(session, behavior_service, user, at(9), at(12), dsa.activity_label_id)
    assert (await task_analysis_service.analyze(session, user, created.task_id)).completion_rate == 100.0


@pytest.mark.asyncio
async def test_analysis_updates_when_task_moves(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await task_service.create(
        session, user, task(at(9), at(10), activity_label_id=dsa.activity_label_id)
    )
    await behavior(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)
    assert (await task_analysis_service.analyze(session, user, created.task_id)).completion_rate == 100.0

    await task_service.update(
        session, user, created.task_id, UpdateTask(start_time=at(14), end_time=at(15))
    )
    assert (await task_analysis_service.analyze(session, user, created.task_id)).completion_rate == 0.0


@pytest.mark.asyncio
async def test_analyze_many_returns_every_task(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    await task_service.create(
        session, user, task(at(9), at(10), title="A", activity_label_id=dsa.activity_label_id)
    )
    await task_service.create(session, user, task(at(14), at(15), title="B"))
    await behavior(session, behavior_service, user, at(9), at(10), dsa.activity_label_id)

    results = await task_analysis_service.analyze_many_for_user(session, user)
    assert len(results) == 2
    assert {r.completion_rate for r in results} == {100.0, 0.0}
    assert all(not hasattr(r, "contributions") for r in results)


@pytest.mark.asyncio
async def test_tasks_may_overlap_each_other_but_analysis_stays_independent(
    session, user, task_service, behavior_service, task_analysis_service
):
    dsa = await make_label(session, user, PrimaryCategory.Study, "DSA")
    wide = await task_service.create(
        session, user, task(at(9), at(12), title="Wide", activity_label_id=dsa.activity_label_id)
    )
    narrow = await task_service.create(
        session, user, task(at(9), at(10), title="Narrow", activity_label_id=dsa.activity_label_id)
    )
    await behavior(session, behavior_service, user, at(9), at(12), dsa.activity_label_id)

    wide_result = await task_analysis_service.analyze(session, user, wide.task_id)
    narrow_result = await task_analysis_service.analyze(session, user, narrow.task_id)
    assert wide_result.completion_rate == 100.0
    assert narrow_result.completion_rate == 100.0


@pytest.mark.asyncio
async def test_analysis_of_another_users_task_is_rejected(
    session, user, other_user, task_service, task_analysis_service
):
    created = await task_service.create(session, other_user, task(at(9), at(12)))
    with pytest.raises(ResourceNotFound):
        await task_analysis_service.analyze(session, user, created.task_id)