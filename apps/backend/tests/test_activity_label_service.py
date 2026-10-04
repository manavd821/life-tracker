from __future__ import annotations

import pytest

from app.core.errors import ResourceConflict, ResourceNotFound
from app.models.enums import PrimaryCategory
from app.schemas.activity_label import CreateActivityLabel, UpdateActivityLabel
from app.schemas.behavior import CreateBehavior
from app.schemas.context_tag import CreateContextTag, UpdateContextTag
from datetime import datetime, timedelta, timezone


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 4, hour, minute, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_create_and_list_labels(session, user, label_service):
    await label_service.create(
        session, user, CreateActivityLabel(
            primary_category=PrimaryCategory.Study, activity_label="DSA"
        )
    )
    labels = await label_service.list_for_user(session, user)
    assert [x.activity_label for x in labels] == ["DSA"]
    assert labels[0].primary_category is PrimaryCategory.Study


@pytest.mark.asyncio
async def test_duplicate_label_in_same_category_rejected(session, user, label_service):
    await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    with pytest.raises(ResourceConflict):
        await label_service.create(
            session, user,
            CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
        )


@pytest.mark.asyncio
async def test_same_label_allowed_in_different_category(session, user, label_service):
    await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="Practice"),
    )
    second = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Work, activity_label="Practice"),
    )
    assert second.activity_label_id is not None


@pytest.mark.asyncio
async def test_labels_are_user_scoped(session, user, other_user, label_service):
    await label_service.create(
        session, other_user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    assert await label_service.list_for_user(session, user) == []


@pytest.mark.asyncio
async def test_update_label(session, user, label_service):
    created = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    updated = await label_service.update(
        session, user, created.activity_label_id,
        UpdateActivityLabel(activity_label="Algorithms"),
    )
    assert updated.activity_label == "Algorithms"


@pytest.mark.asyncio
async def test_update_duplicate_rejected(session, user, label_service):
    await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    second = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="CN"),
    )
    with pytest.raises(ResourceConflict):
        await label_service.update(
            session, user, second.activity_label_id,
            UpdateActivityLabel(activity_label="DSA"),
        )


@pytest.mark.asyncio
async def test_label_of_another_user_not_updatable(session, user, other_user, label_service):
    created = await label_service.create(
        session, other_user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    with pytest.raises(ResourceNotFound):
        await label_service.update(
            session, user, created.activity_label_id,
            UpdateActivityLabel(activity_label="Hacked"),
        )


@pytest.mark.asyncio
async def test_delete_label(session, user, label_service):
    created = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    await label_service.delete(session, user, created.activity_label_id)
    assert await label_service.list_for_user(session, user) == []


@pytest.mark.asyncio
async def test_delete_label_in_use_is_blocked(session, user, label_service, behavior_service):
    created = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    await behavior_service.create(
        session, user,
        CreateBehavior(
            start_time=at(9), end_time=at(10),
            primary_category=PrimaryCategory.Study,
            activity_label_id=created.activity_label_id,
        ),
    )
    with pytest.raises(ResourceConflict) as exc:
        await label_service.delete(session, user, created.activity_label_id)
    assert exc.value.code == "activity_label_in_use"


@pytest.mark.asyncio
async def test_category_change_blocked_when_behaviors_would_break(
    session, user, label_service, behavior_service
):
    created = await label_service.create(
        session, user,
        CreateActivityLabel(primary_category=PrimaryCategory.Study, activity_label="DSA"),
    )
    await behavior_service.create(
        session, user,
        CreateBehavior(
            start_time=at(9), end_time=at(10),
            primary_category=PrimaryCategory.Study,
            activity_label_id=created.activity_label_id,
        ),
    )
    with pytest.raises(ResourceConflict):
        await label_service.update(
            session, user, created.activity_label_id,
            UpdateActivityLabel(primary_category=PrimaryCategory.Work),
        )


@pytest.mark.asyncio
async def test_context_tag_crud(session, user, tag_service):
    created = await tag_service.create(
        session, user,
        CreateContextTag(primary_category=PrimaryCategory.Study, context_tag="Practice"),
    )
    assert (await tag_service.list_for_user(session, user))[0].context_tag == "Practice"

    updated = await tag_service.update(
        session, user, created.behavior_context_tag_id,
        UpdateContextTag(context_tag="Revision"),
    )
    assert updated.context_tag == "Revision"

    await tag_service.delete(session, user, created.behavior_context_tag_id)
    assert await tag_service.list_for_user(session, user) == []


@pytest.mark.asyncio
async def test_duplicate_context_tag_rejected(session, user, tag_service):
    await tag_service.create(
        session, user,
        CreateContextTag(primary_category=PrimaryCategory.Study, context_tag="Practice"),
    )
    with pytest.raises(ResourceConflict):
        await tag_service.create(
            session, user,
            CreateContextTag(primary_category=PrimaryCategory.Study, context_tag="Practice"),
        )


@pytest.mark.asyncio
async def test_context_tag_of_another_user_not_deletable(session, user, other_user, tag_service):
    created = await tag_service.create(
        session, other_user,
        CreateContextTag(primary_category=PrimaryCategory.Study, context_tag="Practice"),
    )
    with pytest.raises(ResourceNotFound):
        await tag_service.delete(session, user, created.behavior_context_tag_id)