from __future__ import annotations

from datetime import datetime, timezone

import pytest


def iso(hour: int, minute: int = 0) -> str:
    return datetime(2026, 10, 4, hour, minute, tzinfo=timezone.utc).isoformat()


pytestmark = pytest.mark.asyncio


async def test_create_behavior_endpoint(client):
    response = await client.post(
        "/api/behaviors",
        json={
            "start_time": iso(9),
            "end_time": iso(10, 30),
            "primary_category": "Study",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["duration_minutes"] == 90
    assert body["source"] == "manual"


async def test_timeline_endpoint(client):
    await client.post(
        "/api/behaviors",
        json={"start_time": iso(9), "end_time": iso(10), "primary_category": "Study"},
    )
    response = await client.get("/api/behaviors", params={"date": "2026-10-04"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_behaviors"] == 1
    assert body["total_tracked_minutes"] == 60
    assert len(body["unaccounted"]) == 2


async def test_overlap_returns_409_with_conflicts(client):
    await client.post(
        "/api/behaviors",
        json={"start_time": iso(9), "end_time": iso(10), "primary_category": "Study"},
    )
    response = await client.post(
        "/api/behaviors",
        json={"start_time": iso(9, 30), "end_time": iso(11), "primary_category": "Study"},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "behavior_overlap"
    assert error["conflicts"]


async def test_invalid_range_returns_422(client):
    response = await client.post(
        "/api/behaviors",
        json={"start_time": iso(10), "end_time": iso(9), "primary_category": "Study"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_time_range"


async def test_naive_datetime_rejected(client):
    response = await client.post(
        "/api/behaviors",
        json={
            "start_time": "2026-10-04T09:00:00",
            "end_time": "2026-10-04T10:00:00",
            "primary_category": "Study",
        },
    )
    assert response.status_code == 422


async def test_patch_and_delete_behavior(client):
    created = (
        await client.post(
            "/api/behaviors",
            json={"start_time": iso(9), "end_time": iso(10), "primary_category": "Study"},
        )
    ).json()

    patched = await client.patch(
        f"/api/behaviors/{created['behavior_id']}",
        json={"end_time": iso(11), "notes": "deep work"},
    )
    assert patched.status_code == 200
    assert patched.json()["duration_minutes"] == 120
    assert patched.json()["source"] == "edit"

    deleted = await client.delete(f"/api/behaviors/{created['behavior_id']}")
    assert deleted.status_code == 204

    assert (await client.get(f"/api/behaviors/{created['behavior_id']}")).status_code == 404


async def test_activity_label_endpoints(client):
    created = await client.post(
        "/api/activity-labels",
        json={"primary_category": "Study", "activity_label": "DSA"},
    )
    assert created.status_code == 201

    duplicate = await client.post(
        "/api/activity-labels",
        json={"primary_category": "Study", "activity_label": "DSA"},
    )
    assert duplicate.status_code == 409

    assert len((await client.get("/api/activity-labels")).json()) == 1

    label_id = created.json()["activity_label_id"]
    assert (await client.delete(f"/api/activity-labels/{label_id}")).status_code == 204
    assert (await client.get("/api/activity-labels")).json() == []


async def test_context_tag_endpoints(client):
    created = await client.post(
        "/api/context-tags",
        json={"primary_category": "Study", "context_tag": "Practice"},
    )
    assert created.status_code == 201
    assert len((await client.get("/api/context-tags")).json()) == 1


async def test_behavior_rejects_naive_and_missing_body(client):
    assert (await client.post("/api/behaviors", json={})).status_code == 422


async def test_unknown_behavior_returns_404(client):
    response = await client.get("/api/behaviors/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def task_body(**overrides):
    body = {
        "title": "DSA Preparation",
        "start_time": iso(9),
        "end_time": iso(12),
        "primary_category": "Study",
    }
    body.update(overrides)
    return body


async def test_task_crud_endpoints(client):
    created = await client.post("/api/tasks", json=task_body())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["planned_minutes"] == 180

    listed = await client.get("/api/tasks", params={"date": "2026-10-04"})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = await client.get(f"/api/tasks/{body['task_id']}")
    assert fetched.status_code == 200

    patched = await client.patch(
        f"/api/tasks/{body['task_id']}", json={"title": "CN reading"}
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "CN reading"
    assert patched.json()["planned_minutes"] == 180

    assert (await client.delete(f"/api/tasks/{body['task_id']}")).status_code == 204
    assert (await client.get(f"/api/tasks/{body['task_id']}")).status_code == 404


async def test_create_task_rejects_invalid_range(client):
    response = await client.post("/api/tasks", json=task_body(start_time=iso(12), end_time=iso(9)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_time_range"


async def test_create_task_rejects_label_from_other_category(client):
    label = (
        await client.post(
            "/api/activity-labels",
            json={"primary_category": "Entertainment", "activity_label": "Gaming"},
        )
    ).json()

    response = await client.post(
        "/api/tasks", json=task_body(activity_label_id=label["activity_label_id"])
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "activity_label_category_mismatch"


async def test_tasks_may_overlap_through_the_api(client):
    first = await client.post("/api/tasks", json=task_body(title="Wide"))
    second = await client.post(
        "/api/tasks", json=task_body(title="Narrow", start_time=iso(10), end_time=iso(11))
    )
    assert first.status_code == 201
    assert second.status_code == 201


async def test_task_analysis_endpoints(client):
    label = (
        await client.post(
            "/api/activity-labels",
            json={"primary_category": "Study", "activity_label": "DSA"},
        )
    ).json()

    task = (await client.post("/api/tasks", json=task_body(activity_label_id=label["activity_label_id"]))).json()

    empty = await client.get(f"/api/tasks/{task['task_id']}/analysis")
    assert empty.status_code == 200
    assert empty.json() == {
        "task_id": task["task_id"],
        "planned_minutes": 180,
        "effective_minutes": 0.0,
        "completion_rate": 0.0,
        "contributions": [],
    }

    await client.post(
        "/api/behaviors",
        json={
            "start_time": iso(10),
            "end_time": iso(11),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )

    analyzed = (await client.get(f"/api/tasks/{task['task_id']}/analysis")).json()
    assert analyzed["effective_minutes"] == 60.0
    assert analyzed["completion_rate"] == 33.33
    assert analyzed["contributions"][0]["match_score"] == 1.0

    listed = await client.get("/api/tasks/analysis")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "task_id": task["task_id"],
            "planned_minutes": 180,
            "effective_minutes": 60.0,
            "completion_rate": 33.33,
        }
    ]


async def test_unknown_task_returns_404(client):
    assert (await client.get("/api/tasks/00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_daily_analytics_empty_day(client):
    response = await client.get("/api/analytics/daily", params={"date": "2026-10-04"})
    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-10-04",
        "summary": {
            "day_minutes": 1440,
            "tracked_minutes": 0,
            "unaccounted_minutes": 1440,
            "behavior_count": 0,
        },
        "categories": [],
        "activities": [],
        "tasks": {
            "count": 0,
            "planned_minutes": 0,
            "effective_minutes": 0.0,
            "completion_rate": 0.0,
        },
    }


async def test_daily_analytics_requires_a_date(client):
    assert (await client.get("/api/analytics/daily")).status_code == 422


async def test_daily_analytics_rejects_malformed_date(client):
    response = await client.get("/api/analytics/daily", params={"date": "not-a-date"})
    assert response.status_code == 422


async def test_daily_analytics_endpoint_aggregates(client):
    label = (
        await client.post(
            "/api/activity-labels",
            json={"primary_category": "Study", "activity_label": "DSA"},
        )
    ).json()

    await client.post(
        "/api/behaviors",
        json={
            "start_time": iso(9),
            "end_time": iso(10),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )
    await client.post(
        "/api/behaviors",
        json={"start_time": iso(11), "end_time": iso(12), "primary_category": "Work"},
    )
    await client.post("/api/tasks", json=task_body(activity_label_id=label["activity_label_id"]))

    body = (await client.get("/api/analytics/daily", params={"date": "2026-10-04"})).json()

    assert body["summary"] == {
        "day_minutes": 1440,
        "tracked_minutes": 120,
        "unaccounted_minutes": 1320,
        "behavior_count": 2,
    }
    assert body["categories"] == [
        {"category": "Study", "duration_minutes": 60},
        {"category": "Work", "duration_minutes": 60},
    ]
    assert body["activities"] == [
        {"category": "Study", "activity_label": "DSA", "duration_minutes": 60},
        {"category": "Work", "activity_label": None, "duration_minutes": 60},
    ]
    assert body["tasks"] == {
        "count": 1,
        "planned_minutes": 180,
        "effective_minutes": 60.0,
        "completion_rate": 33.33,
    }


async def test_pattern_transitions_endpoint_is_empty_without_data(client):
    response = await client.get(
        "/api/patterns/transitions",
        params={"start_date": "2026-10-04", "end_date": "2026-10-08"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "window": {"start_date": "2026-10-04", "end_date": "2026-10-08", "behavior_count": 0},
        "minimum_transition_count": 5,
        "category_transitions": [],
        "activity_transitions": [],
    }


async def test_pattern_transitions_endpoint_counts_transitions(client):
    for day in (4, 5, 6, 7, 8):
        await client.post(
            "/api/behaviors",
            json={
                "start_time": datetime(2026, 10, day, 9, tzinfo=timezone.utc).isoformat(),
                "end_time": datetime(2026, 10, day, 10, tzinfo=timezone.utc).isoformat(),
                "primary_category": "Study",
            },
        )
        await client.post(
            "/api/behaviors",
            json={
                "start_time": datetime(2026, 10, day, 10, tzinfo=timezone.utc).isoformat(),
                "end_time": datetime(2026, 10, day, 11, tzinfo=timezone.utc).isoformat(),
                "primary_category": "Entertainment",
            },
        )

    body = (
        await client.get(
            "/api/patterns/transitions",
            params={"start_date": "2026-10-04", "end_date": "2026-10-08"},
        )
    ).json()

    assert body["window"]["behavior_count"] == 10
    assert body["category_transitions"] == [
        {
            "type": "category_transition",
            "from_category": "Study",
            "to_category": "Entertainment",
            "count": 5,
            "probability": 1.0,
            "transitions_from_source": 5,
        }
    ]


async def test_pattern_context_endpoint_returns_descriptive_stats(client):
    label = (
        await client.post(
            "/api/activity-labels",
            json={"primary_category": "Study", "activity_label": "CN"},
        )
    ).json()

    for index in range(3):
        await client.post(
            "/api/behaviors",
            json={
                "start_time": datetime(2026, 10, 4 + index, 9, tzinfo=timezone.utc).isoformat(),
                "end_time": datetime(2026, 10, 4 + index, 10, 30, tzinfo=timezone.utc).isoformat(),
                "primary_category": "Study",
                "activity_label_id": label["activity_label_id"],
                "environment": "Library",
            },
        )

    body = (
        await client.get(
            "/api/patterns/context",
            params={"start_date": "2026-10-04", "end_date": "2026-10-06"},
        )
    ).json()

    assert body["minimum_context_sessions"] == 3
    assert body["context_stats"] == [
        {
            "type": "context_stat",
            "category": "Study",
            "activity_label": "CN",
            "dimension": "environment",
            "context": "Library",
            "session_count": 3,
            "total_duration_minutes": 270,
            "average_duration_minutes": 90.0,
        }
    ]
    assert body["associations"] == []


async def test_pattern_endpoints_reject_inverted_range(client):
    response = await client.get(
        "/api/patterns/transitions",
        params={"start_date": "2026-10-08", "end_date": "2026-10-04"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pattern_range"


async def test_pattern_endpoints_reject_malformed_date(client):
    assert (
        await client.get("/api/patterns/context", params={"start_date": "nope"})
    ).status_code == 422


async def test_daily_analytics_filters_by_date(client):
    await client.post(
        "/api/behaviors",
        json={"start_time": iso(9), "end_time": iso(10), "primary_category": "Study"},
    )

    same_day = (await client.get("/api/analytics/daily", params={"date": "2026-10-04"})).json()
    other_day = (await client.get("/api/analytics/daily", params={"date": "2026-10-05"})).json()

    assert same_day["summary"]["behavior_count"] == 1
    assert other_day["summary"]["behavior_count"] == 0
    assert other_day["summary"]["unaccounted_minutes"] == 1440
    assert other_day["date"] == "2026-10-05"