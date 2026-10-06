from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.errors import InvalidTimeRange
from app.models.enums import (
    EmotionState,
    EnergyLevel,
    Environment,
    FocusState,
    PrimaryCategory,
)
from app.repositories.activity_label_repository import ActivityLabelRepository
from app.repositories.behavior_repository import BehaviorRepository
from app.schemas.behavior import CreateBehavior
from app.services.pattern_detection_service import PatternDetectionService

TZ = timezone.utc
DAY = date(2026, 10, 4)
WEEK = (date(2026, 10, 4), date(2026, 10, 8))


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
    environment=None,
    energy_level=None,
    focus_state=None,
    emotion_state=None,
):
    return await behavior_service.create(
        session,
        user_id,
        CreateBehavior(
            start_time=start,
            end_time=end,
            primary_category=category,
            activity_label_id=label_id,
            environment=environment,
            energy_level=energy_level,
            focus_state=focus_state,
            emotion_state=emotion_state,
        ),
    )


def service(**kwargs) -> PatternDetectionService:
    return PatternDetectionService(BehaviorRepository(), **kwargs)


def counts(patterns) -> dict[tuple[str, str], int]:
    return {
        (p.from_category.value, p.to_category.value): p.count
        for p in patterns.category_transitions
    }


# ---------- category transitions ----------


@pytest.mark.asyncio
async def test_no_behaviors_means_no_patterns(session, user, behavior_service):
    result = await service().transitions(session, user, DAY)

    assert result.window.start_date == "2026-10-04"
    assert result.window.end_date == "2026-10-04"
    assert result.window.behavior_count == 0
    assert result.category_transitions == []
    assert result.activity_transitions == []

    context = await service().context(session, user, DAY)
    assert context.window.behavior_count == 0
    assert context.context_stats == []
    assert context.associations == []


@pytest.mark.asyncio
async def test_category_transitions_are_counted(session, user, behavior_service):
    # five clean Study -> Entertainment transitions
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
        )

    result = await service().transitions(session, user, *WEEK)

    assert counts(result) == {("Study", "Entertainment"): 5}
    transition = result.category_transitions[0]
    assert transition.type == "category_transition"
    assert transition.probability == 1.0
    assert transition.transitions_from_source == 5


@pytest.mark.asyncio
async def test_same_category_consecutive_behaviors_are_normalized(
    session, user, behavior_service
):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    cn = await labels.add(session, user, "Study", "CN")

    for day in (4, 5, 6, 7, 8):
        start = at(9, day=day)
        await record(session, behavior_service, user, start, start + timedelta(hours=1), dsa.activity_label_id)
        await record(
            session,
            behavior_service,
            user,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
            cn.activity_label_id,
        )
        await record(
            session,
            behavior_service,
            user,
            start + timedelta(hours=2),
            start + timedelta(hours=3),
            category=PrimaryCategory.Work,
        )

    result = await service().transitions(session, user, *WEEK)

    # DSA -> CN is collapsed into a single Study step, so only Study -> Work is left
    assert counts(result) == {("Study", "Work"): 5}
    assert all(
        p.from_category != p.to_category for p in result.category_transitions
    )


@pytest.mark.asyncio
async def test_unaccounted_gap_does_not_create_a_transition(
    session, user, behavior_service
):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        # 10:00 -> 11:00 is unaccounted, so Study -> Entertainment is not real
        await record(
            session,
            behavior_service,
            user,
            at(11, day=day),
            at(12, day=day),
            category=PrimaryCategory.Entertainment,
        )

    result = await service().transitions(session, user, *WEEK)

    assert counts(result) == {}
    assert result.window.behavior_count == 10


@pytest.mark.asyncio
async def test_gap_breaks_the_chain_but_later_transitions_survive(
    session, user, behavior_service
):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(12, day=day),
            at(13, day=day),
            category=PrimaryCategory.Rest,
        )
        await record(
            session,
            behavior_service,
            user,
            at(13, day=day),
            at(14, day=day),
            category=PrimaryCategory.Work,
        )

    result = await service().transitions(session, user, *WEEK)

    assert counts(result) == {("Rest", "Work"): 5}


@pytest.mark.asyncio
async def test_transition_probability_is_conditional(session, user, behavior_service):
    # Study -> Entertainment 3x, Study -> Rest 2x over separate days
    for day, second in ((4, "Entertainment"), (5, "Entertainment"), (6, "Entertainment"), (7, "Rest"), (8, "Rest")):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory(second),
        )

    result = await service(min_transition_count=1).transitions(session, user, *WEEK)

    rows = counts(result)
    assert rows == {("Study", "Entertainment"): 3, ("Study", "Rest"): 2}
    probabilities = {
        (p.from_category.value, p.to_category.value): p.probability
        for p in result.category_transitions
    }
    assert probabilities[("Study", "Entertainment")] == 0.6
    assert probabilities[("Study", "Rest")] == 0.4
    assert sum(probabilities.values()) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_minimum_transition_threshold_is_respected(
    session, user, behavior_service
):
    for day in (4, 5, 6, 7):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
        )

    strict = await service(min_transition_count=5).transitions(session, user, *WEEK)
    assert counts(strict) == {}

    loose = await service(min_transition_count=4).transitions(session, user, *WEEK)
    assert counts(loose) == {("Study", "Entertainment"): 4}
    assert strict.minimum_transition_count == 5


# ---------- activity transitions ----------


@pytest.mark.asyncio
async def test_activity_transitions(session, user, behavior_service):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    cn = await labels.add(session, user, "Study", "CN")
    youtube = await labels.add(session, user, "Entertainment", "YouTube")

    for day in (4, 5, 6, 7, 8):
        start = at(9, day=day)
        await record(session, behavior_service, user, start, start + timedelta(hours=1), dsa.activity_label_id)
        await record(
            session,
            behavior_service,
            user,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
            cn.activity_label_id,
        )
        await record(
            session,
            behavior_service,
            user,
            start + timedelta(hours=2),
            start + timedelta(hours=3),
            youtube.activity_label_id,
            category=PrimaryCategory.Entertainment,
        )

    result = await service().transitions(session, user, *WEEK)

    activity = {
        (p.from_activity, p.to_activity): p.count for p in result.activity_transitions
    }
    assert activity == {("DSA", "CN"): 5, ("CN", "YouTube"): 5}
    # the category level collapsed DSA -> CN into one Study step
    assert counts(result) == {("Study", "Entertainment"): 5}
    dsa_cn = next(p for p in result.activity_transitions if p.from_activity == "DSA")
    assert dsa_cn.from_category is PrimaryCategory.Study
    assert dsa_cn.to_activity == "CN"


@pytest.mark.asyncio
async def test_missing_activity_label_breaks_the_activity_chain(
    session, user, behavior_service
):
    labels = ActivityLabelRepository()
    dsa = await labels.add(session, user, "Study", "DSA")
    cn = await labels.add(session, user, "Study", "CN")

    for day in (4, 5, 6, 7, 8):
        start = at(9, day=day)
        await record(session, behavior_service, user, start, start + timedelta(hours=1), dsa.activity_label_id)
        # unlabelled Study in the middle: no invented activity, no DSA -> CN
        await record(
            session, behavior_service, user, start + timedelta(hours=1), start + timedelta(hours=2)
        )
        await record(
            session,
            behavior_service,
            user,
            start + timedelta(hours=2),
            start + timedelta(hours=3),
            cn.activity_label_id,
        )

    result = await service().transitions(session, user, *WEEK)

    assert result.activity_transitions == []
    assert counts(result) == {}


@pytest.mark.asyncio
async def test_unlabelled_behaviors_produce_no_activity_names(
    session, user, behavior_service
):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Work,
        )

    result = await service().transitions(session, user, *WEEK)

    assert result.activity_transitions == []
    assert counts(result) == {("Study", "Work"): 5}


# ---------- date ranges ----------


@pytest.mark.asyncio
async def test_date_range_covers_every_day(session, user, behavior_service):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
        )

    single = await service().transitions(session, user, DAY, date(2026, 10, 4))
    assert single.window.behavior_count == 2

    ranged = await service().transitions(
        session, user, date(2026, 10, 4), date(2026, 10, 8)
    )
    assert ranged.window.start_date == "2026-10-04"
    assert ranged.window.end_date == "2026-10-08"
    assert ranged.window.behavior_count == 10
    assert counts(ranged) == {("Study", "Entertainment"): 5}


@pytest.mark.asyncio
async def test_end_date_defaults_to_start_date(session, user, behavior_service):
    result = await service().transitions(
        session, user, start_date=date(2026, 10, 4), end_date=None
    )
    assert result.window.start_date == result.window.end_date == "2026-10-04"


@pytest.mark.asyncio
async def test_inverted_range_is_rejected(session, user):
    with pytest.raises(InvalidTimeRange):
        await service().transitions(
            session, user, date(2026, 10, 8), date(2026, 10, 4)
        )


@pytest.mark.asyncio
async def test_behaviors_outside_the_range_are_excluded(
    session, user, behavior_service
):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
        )

    result = await service().transitions(
        session, user, date(2026, 10, 4), date(2026, 10, 5)
    )
    assert result.window.behavior_count == 4
    assert counts(result) == {}


@pytest.mark.asyncio
async def test_soft_deleted_behaviors_are_ignored(session, user, behavior_service):
    for day in (4, 5, 6, 7, 8):
        created = await record(
            session, behavior_service, user, at(9, day=day), at(10, day=day)
        )
        await behavior_service.delete(session, user, created.behavior_id)
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
        )

    result = await service().transitions(session, user, *WEEK)
    assert result.window.behavior_count == 5
    assert result.category_transitions == []


# ---------- context associations ----------


@pytest.mark.asyncio
async def test_context_averages_are_correct(session, user, behavior_service):
    labels = ActivityLabelRepository()
    cn = await labels.add(session, user, "Study", "CN")

    for index in range(8):
        start = at(9) + timedelta(days=index, hours=1)
        await record(
            session,
            behavior_service,
            user,
            start,
            start + timedelta(minutes=96),
            cn.activity_label_id,
            environment=Environment.Library,
        )
    for index in range(7):
        start = at(12) + timedelta(days=index, hours=1)
        await record(
            session,
            behavior_service,
            user,
            start,
            start + timedelta(minutes=48),
            cn.activity_label_id,
            environment=Environment.Home,
        )

    result = await service().context(
        session, user, date(2026, 10, 4), date(2026, 10, 11)
    )

    rows = {
        (s.dimension, s.context): s for s in result.context_stats
    }
    library = rows[("environment", "Library")]
    home = rows[("environment", "Home")]
    assert library.session_count == 8
    assert library.total_duration_minutes == 768
    assert library.average_duration_minutes == 96.0
    assert library.activity_label == "CN"
    assert home.session_count == 7
    assert home.average_duration_minutes == 48.0

    assert len(result.associations) == 1
    association = result.associations[0]
    assert association.type == "context_association"
    assert association.activity_label == "CN"
    assert association.dimension == "environment"
    assert association.context_a == "Library"
    assert association.context_b == "Home"
    assert association.average_duration_a == 96.0
    assert association.average_duration_b == 48.0
    assert association.sample_a == 8
    assert association.sample_b == 7
    assert association.difference_minutes == 48.0


@pytest.mark.asyncio
async def test_all_context_dimensions_are_described(session, user, behavior_service):
    labels = ActivityLabelRepository()
    cn = await labels.add(session, user, "Study", "CN")

    for index in range(3):
        start = at(9) + timedelta(days=index, hours=1)
        await record(
            session,
            behavior_service,
            user,
            start,
            start + timedelta(minutes=90),
            cn.activity_label_id,
            environment=Environment.Library,
            energy_level=EnergyLevel.High,
            focus_state=FocusState.Focused,
            emotion_state=EmotionState.Calm,
        )

    result = await service().context(
        session, user, date(2026, 10, 4), date(2026, 10, 6)
    )

    by_dimension = {s.dimension: s for s in result.context_stats}
    assert by_dimension["environment"].context == "Library"
    assert by_dimension["energy_level"].context == "High"
    assert by_dimension["focus_state"].context == "Focused"
    assert by_dimension["emotion_state"].context == "Calm"
    assert all(s.average_duration_minutes == 90.0 for s in result.context_stats)
    # only one context per dimension means no comparison to report
    assert result.associations == []


@pytest.mark.asyncio
async def test_context_minimum_sessions_is_respected(session, user, behavior_service):
    labels = ActivityLabelRepository()
    cn = await labels.add(session, user, "Study", "CN")

    for index in range(3):
        start = at(9) + timedelta(days=index, hours=1)
        await record(
            session,
            behavior_service,
            user,
            start,
            start + timedelta(minutes=120),
            cn.activity_label_id,
            environment=Environment.Library,
        )
    start = at(12)
    await record(
        session,
        behavior_service,
        user,
        start,
        start + timedelta(minutes=10),
        cn.activity_label_id,
        environment=Environment.Home,
    )

    strict = await service(min_context_sessions=2).context(
        session, user, date(2026, 10, 4), date(2026, 10, 6)
    )
    # the single Home session is still described, but too small to compare
    assert {s.context for s in strict.context_stats} == {"Library", "Home"}
    assert strict.associations == []

    loose = await service(min_context_sessions=1).context(
        session, user, date(2026, 10, 4), date(2026, 10, 6)
    )
    assert {s.context for s in loose.context_stats} == {"Library", "Home"}
    assert loose.associations[0].context_a == "Library"


@pytest.mark.asyncio
async def test_context_stats_keep_unlabelled_behaviours_without_a_name(
    session, user, behavior_service
):
    for index in range(3):
        start = at(9) + timedelta(days=index, hours=1)
        await record(
            session,
            behavior_service,
            user,
            start,
            start + timedelta(minutes=45),
            environment=Environment.Home,
        )

    result = await service().context(
        session, user, date(2026, 10, 4), date(2026, 10, 6)
    )

    assert [s.activity_label for s in result.context_stats] == [None]
    assert result.context_stats[0].session_count == 3


# ---------- isolation ----------


@pytest.mark.asyncio
async def test_patterns_are_scoped_to_one_user(
    session, user, other_user, behavior_service
):
    for day in (4, 5, 6, 7, 8):
        await record(session, behavior_service, user, at(9, day=day), at(10, day=day))
        await record(
            session,
            behavior_service,
            user,
            at(10, day=day),
            at(11, day=day),
            category=PrimaryCategory.Entertainment,
            environment=Environment.Library,
        )
        await record(
            session,
            behavior_service,
            other_user,
            at(9, day=day),
            at(13, day=day),
            category=PrimaryCategory.Rest,
            environment=Environment.Gym,
        )

    mine = await service().transitions(session, user, date(2026, 10, 4), date(2026, 10, 8))
    assert counts(mine) == {("Study", "Entertainment"): 5}

    mine_context = await service().context(
        session, user, date(2026, 10, 4), date(2026, 10, 8)
    )
    assert {s.context for s in mine_context.context_stats} == {"Library"}

    theirs = await service().transitions(
        session, other_user, date(2026, 10, 4), date(2026, 10, 8)
    )
    assert theirs.category_transitions == []

    theirs_context = await service().context(
        session, other_user, date(2026, 10, 4), date(2026, 10, 8)
    )
    assert {s.context for s in theirs_context.context_stats} == {"Gym"}
