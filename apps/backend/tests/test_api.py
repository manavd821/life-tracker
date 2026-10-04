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