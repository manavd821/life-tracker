from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import BehaviorOverlapError, InvalidTimeRange, ResourceNotFound
from app.models.enums import Precision, PrimaryCategory
from app.schemas.behavior import CreateBehavior

DAY_TZ = timezone(timedelta(hours=5, minutes=30))
DAY_OFFSET_MINUTES = 330


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 4, hour, minute, tzinfo=DAY_TZ)


def payload(start: datetime, end: datetime, **overrides) -> CreateBehavior:
    data = {
        "start_time": start,
        "end_time": end,
        "primary_category": PrimaryCategory.Study,
    }
    data.update(overrides)
    return CreateBehavior(**data)


async def make_label(session, user_id, category, name):
    from app.repositories.activity_label_repository import ActivityLabelRepository

    return await ActivityLabelRepository().add(session, user_id, category.value, name)


async def make_tag(session, user_id, category, name):
    from app.repositories.context_tag_repository import ContextTagRepository

    return await ContextTagRepository().add(session, user_id, category.value, name)


@pytest.mark.asyncio
async def test_create_behavior(session, user, behavior_service):
    response = await behavior_service.create(session, user, payload(at(9), at(10, 30)))

    assert response.start_time == at(9)
    assert response.duration_minutes == 90
    assert response.source.value == "manual"
    assert response.precision is Precision.HIGH


@pytest.mark.asyncio
async def test_duration_is_derived_not_trusted(session, user, behavior_service):
    extra = {f"duration_minutes": 999, "extra_field": "x"}
    response = await behavior_service.create(
        session, user, payload(at(9), at(10, 30), **extra)
    )
    assert response.duration_minutes == 90


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end",
    [
        (at(9, 30), at(9)),          # start after end
        (at(9), at(9)),              # zero length
        (at(10), at(9)),             # inverted
    ],
)
async def test_start_must_be_before_end(session, user, behavior_service, start, end):
    with pytest.raises(InvalidTimeRange):
        await behavior_service.create(session, user, payload(start, end))


@pytest.mark.asyncio
async def test_adjacent_behaviors_allowed(session, user, behavior_service):
    await behavior_service.create(session, user, payload(at(9), at(10)))
    response = await behavior_service.create(session, user, payload(at(10), at(11)))
    assert response.duration_minutes == 60


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end",
    [
        (at(9, 30), at(10, 30)),   # partial overlap
        (at(9), at(10)),           # exact duplicate
        (at(8), at(12)),           # containing
        (at(8, 30), at(9, 30)),    # contained
        (at(9), at(10, 1)),        # one minute past the end
        (at(8, 59), at(10)),       # one minute before the start
    ],
)
async def test_overlapping_behaviors_rejected(session, user, behavior_service, start, end):
    await behavior_service.create(session, user, payload(at(9), at(10)))
    with pytest.raises(BehaviorOverlapError):
        await behavior_service.create(session, user, payload(start, end))


@pytest.mark.asyncio
async def test_overlap_error_lists_conflicts(session, user, behavior_service):
    label = await make_label(session, user, PrimaryCategory.Study, "DSA")
    await behavior_service.create(
        session, user, payload(at(9), at(10, 30), activity_label_id=label.activity_label_id)
    )
    with pytest.raises(BehaviorOverlapError) as exc:
        await behavior_service.create(session, user, payload(at(10), at(11)))

    assert exc.value.status_code == 409
    assert exc.value.details["conflicts"]
    assert "DSA" in exc.value.details["conflicts"][0]


@pytest.mark.asyncio
async def test_deleted_behavior_does_not_block_overlap(session, user, behavior_service):
    created = await behavior_service.create(session, user, payload(at(9), at(10)))
    await behavior_service.delete(session, user, created.behavior_id)

    response = await behavior_service.create(session, user, payload(at(9), at(10)))
    assert response.behavior_id != created.behavior_id


@pytest.mark.asyncio
async def test_deleted_behavior_absent_from_timeline(session, user, behavior_service):
    from datetime import date

    created = await behavior_service.create(session, user, payload(at(9), at(10)))
    await behavior_service.delete(session, user, created.behavior_id)

    timeline = await behavior_service.timeline(session, user, date(2026, 10, 4), DAY_OFFSET_MINUTES)
    assert timeline.total_behaviors == 0


@pytest.mark.asyncio
async def test_activity_label_from_another_user_rejected(session, user, other_user, behavior_service):
    label = await make_label(session, other_user, PrimaryCategory.Study, "DSA")
    with pytest.raises(ResourceNotFound):
        await behavior_service.create(
            session, user, payload(at(9), at(10), activity_label_id=label.activity_label_id)
        )


@pytest.mark.asyncio
async def test_activity_label_wrong_category_rejected(session, user, behavior_service):
    label = await make_label(session, user, PrimaryCategory.Entertainment, "Gaming")
    with pytest.raises(InvalidTimeRange) as exc:
        await behavior_service.create(
            session, user, payload(at(9), at(10), activity_label_id=label.activity_label_id)
        )
    assert exc.value.code == "activity_label_category_mismatch"


@pytest.mark.asyncio
async def test_context_tag_from_another_user_rejected(session, user, other_user, behavior_service):
    tag = await make_tag(session, other_user, PrimaryCategory.Study, "Notes")
    with pytest.raises(ResourceNotFound):
        await behavior_service.create(
            session, user, payload(at(9), at(10), context_tag_ids=[tag.behavior_context_tag_id])
        )


@pytest.mark.asyncio
async def test_context_tag_wrong_category_rejected(session, user, behavior_service):
    tag = await make_tag(session, user, PrimaryCategory.Entertainment, "Scrolling")
    with pytest.raises(InvalidTimeRange) as exc:
        await behavior_service.create(
            session, user, payload(at(9), at(10), context_tag_ids=[tag.behavior_context_tag_id])
        )
    assert exc.value.code == "context_tag_category_mismatch"


@pytest.mark.asyncio
async def test_context_tags_are_attached(session, user, behavior_service):
    tag = await make_tag(session, user, PrimaryCategory.Study, "Practice")
    response = await behavior_service.create(
        session, user, payload(at(9), at(10), context_tag_ids=[tag.behavior_context_tag_id])
    )
    assert [t.context_tag for t in response.context_tags] == ["Practice"]


@pytest.mark.asyncio
async def test_behavior_of_another_user_not_readable(session, user, other_user, behavior_service):
    created = await behavior_service.create(session, other_user, payload(at(9), at(10)))
    with pytest.raises(ResourceNotFound):
        await behavior_service.get(session, user, created.behavior_id)


@pytest.mark.asyncio
async def test_behavior_of_another_user_not_updatable(session, user, other_user, behavior_service):
    from app.schemas.behavior import UpdateBehavior

    created = await behavior_service.create(session, other_user, payload(at(9), at(10)))
    with pytest.raises(ResourceNotFound):
        await behavior_service.update(
            session, user, created.behavior_id, UpdateBehavior(notes="hacked")
        )


@pytest.mark.asyncio
async def test_timeline_gap_calculation(session, user, behavior_service):
    from datetime import date

    await behavior_service.create(session, user, payload(at(9), at(10)))
    await behavior_service.create(session, user, payload(at(10, 30), at(12)))

    timeline = await behavior_service.timeline(session, user, date(2026, 10, 4), DAY_OFFSET_MINUTES)
    assert timeline.total_behaviors == 2
    assert timeline.total_tracked_minutes == 150
    # whole day minus the two tracked blocks
    assert timeline.total_unaccounted_minutes == 1440 - 150
    assert len(timeline.unaccounted) == 3
    assert timeline.unaccounted[0].duration_minutes == 540      # 00:00 -> 09:00
    assert timeline.unaccounted[1].duration_minutes == 30       # 10:00 -> 10:30
    assert timeline.unaccounted[2].duration_minutes == 720      # 12:00 -> 24:00


@pytest.mark.asyncio
async def test_timeline_no_gaps_when_day_full(session, user, behavior_service):
    from datetime import date

    end_of_day = datetime(2026, 10, 5, tzinfo=DAY_TZ)
    await behavior_service.create(session, user, payload(at(0), end_of_day))
    timeline = await behavior_service.timeline(session, user, date(2026, 10, 4), DAY_OFFSET_MINUTES)
    assert timeline.unaccounted == []
    assert timeline.total_unaccounted_minutes == 0


@pytest.mark.asyncio
async def test_timeline_ordering(session, user, behavior_service):
    from datetime import date

    await behavior_service.create(session, user, payload(at(11), at(12)))
    await behavior_service.create(session, user, payload(at(9), at(10)))

    timeline = await behavior_service.timeline(session, user, date(2026, 10, 4), DAY_OFFSET_MINUTES)
    assert [b.start_time for b in timeline.behaviors] == [at(9), at(11)]


@pytest.mark.asyncio
async def test_update_revalidates_overlap(session, user, behavior_service):
    from app.schemas.behavior import UpdateBehavior

    await behavior_service.create(session, user, payload(at(9), at(10)))
    second = await behavior_service.create(session, user, payload(at(11), at(12)))

    with pytest.raises(BehaviorOverlapError):
        await behavior_service.update(
            session, user, second.behavior_id, UpdateBehavior(start_time=at(9, 30), end_time=at(11))
        )


@pytest.mark.asyncio
async def test_update_allows_own_interval(session, user, behavior_service):
    from app.schemas.behavior import UpdateBehavior

    created = await behavior_service.create(session, user, payload(at(9), at(10)))
    response = await behavior_service.update(
        session, user, created.behavior_id, UpdateBehavior(end_time=at(11))
    )
    assert response.duration_minutes == 120
    assert response.source.value == "edit"


@pytest.mark.asyncio
async def test_update_revalidates_category_on_label(session, user, behavior_service):
    from app.schemas.behavior import UpdateBehavior

    label = await make_label(session, user, PrimaryCategory.Study, "DSA")
    created = await behavior_service.create(
        session, user, payload(at(9), at(10), activity_label_id=label.activity_label_id)
    )
    with pytest.raises(InvalidTimeRange):
        await behavior_service.update(
            session, user, created.behavior_id,
            UpdateBehavior(primary_category=PrimaryCategory.Work),
        )


@pytest.mark.asyncio
async def test_freed_interval_can_be_reused_after_delete(session, user, behavior_service):
    first = await behavior_service.create(session, user, payload(at(8), at(10)))
    await behavior_service.delete(session, user, first.behavior_id)

    response = await behavior_service.create(session, user, payload(at(8), at(13)))
    assert response.duration_minutes == 300


@pytest.mark.asyncio
async def test_other_users_behaviors_do_not_block_overlap(session, user, other_user, behavior_service):
    await behavior_service.create(session, other_user, payload(at(9), at(10)))
    response = await behavior_service.create(session, user, payload(at(9), at(10)))
    assert response.behavior_id is not None