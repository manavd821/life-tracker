"""Deterministic demo data for one existing user. Development only.

Resolves an existing application user from a Clerk user id and inserts activity
labels, context tags, behaviors, behavior-context mappings, tasks, and
task-context mappings. Nothing derived is stored: analytics, task analysis,
patterns, insights, and chat context are always computed by the existing
engines.

Usage (from apps/backend):

    uv run python -m scripts.seed_demo_data --clerk-user-id user_xxx
    uv run python -m scripts.seed_demo_data --clerk-user-id user_xxx --reset
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import random
import sys
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, loop_factory
from app.models import (
    ActivityLabel,
    Behavior,
    BehaviorContextTag,
    BehaviorContextTagMap,
    Task,
    TaskContextTagMap,
)
from app.models.enums import (
    BehaviorSource,
    EmotionState,
    EnergyLevel,
    Environment,
    FocusState,
    Precision,
    PrimaryCategory,
)
from app.repositories.activity_label_repository import ActivityLabelRepository
from app.repositories.behavior_repository import BehaviorRepository
from app.repositories.context_tag_repository import ContextTagRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_context_builder import AIContextBuilder, render_chat_context
from app.services.analytics_service import AnalyticsService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.task_analysis_service import TaskAnalysisService

DEFAULT_DAYS = 42
DEFAULT_SEED = "life-tracker-demo"
MIN_DAYS = 14
MAX_DAYS = 365

# Reset scans a wider window than any allowed --days so rows created by an
# earlier run (possibly with a different range) are always found again.
RESET_WINDOW_DAYS = 740
# A day never has more than 10 sessions or 4 tasks; the extra keys keep the
# id superset stable if a template grows.
DEMO_BEHAVIOR_KEYS = tuple(f"s{i}" for i in range(20))
DEMO_TASK_KEYS = tuple(f"t{i}" for i in range(10))

SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "life-tracker.dev/seed-demo")
CHAIN_JITTER = (-10, -5, -5, 0, 0, 0, 5, 5, 10)
DURATION_JITTER = (-15, -10, -5, 0, 0, 0, 5, 10, 15)
MIN_SESSION_MINUTES = 30
APPROXIMATE_KINDS = ("watch", "game")

STUDY, HEALTH, ENTERTAINMENT, WORK = (
    PrimaryCategory.Study,
    PrimaryCategory.Health,
    PrimaryCategory.Entertainment,
    PrimaryCategory.Work,
)
LIBRARY, HOME, COLLEGE, PG, GYM = (
    Environment.Library,
    Environment.Home,
    Environment.College,
    Environment.PG,
    Environment.Gym,
)


class SeedError(Exception):
    pass


# --------------------------------------------------------------------------
# Day templates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    key: str
    start: str
    minutes: int
    category: PrimaryCategory
    label: str | None
    environment: Environment | None
    tags: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class Chain:
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class TaskPlan:
    title: str
    category: PrimaryCategory
    label: str | None
    tags: tuple[str, ...]
    strategy: str  # inside | clock | window
    ref: str | None = None
    window: tuple[str, str] | None = None
    offset: int = 0
    description: str | None = None


@dataclass(frozen=True)
class Template:
    chains: tuple[Chain, ...]
    tasks: tuple[TaskPlan, ...]


# The dense template intentionally packs Study -> Study -> Entertainment and
# Ent -> Health into one day so single-day pattern queries clear the threshold.
DENSE = Template(
    chains=(
        Chain(
            (
                Slot("s0", "07:00", 60, HEALTH, "Gym", GYM, ("Gym", "Morning"), "gym"),
                Slot("s1", "08:00", 105, STUDY, "DSA", LIBRARY, ("Library", "LeetCode", "Morning"), "study_library"),
                Slot("s2", "09:45", 75, STUDY, "DBMS", LIBRARY, ("Library", "Exam Preparation"), "study_library"),
                Slot("s3", "11:00", 45, ENTERTAINMENT, "YouTube", HOME, ("Home",), "watch"),
            )
        ),
        Chain(
            (
                Slot("s4", "14:00", 120, WORK, "Project Development", PG, ("Project Work", "PG"), "work"),
                Slot("s5", "16:00", 60, ENTERTAINMENT, "Gaming", PG, ("PG", "Evening"), "game"),
            )
        ),
        Chain(
            (
                Slot("s6", "18:30", 90, STUDY, "System Design", HOME, ("Home", "Evening"), "study_home"),
                Slot("s7", "20:00", 45, STUDY, "DSA", PG, ("PG", "LeetCode", "Evening"), "study_pg"),
                Slot("s8", "20:45", 60, ENTERTAINMENT, "YouTube", PG, ("PG", "Evening"), "watch"),
                Slot("s9", "21:45", 30, HEALTH, "Walking", None, ("Evening", "Outdoor"), "walk"),
            )
        ),
    ),
    tasks=(
        TaskPlan("DSA Practice", STUDY, "DSA", ("Library",), "clock", ref="s1"),
        TaskPlan("Gym", HEALTH, "Gym", ("Gym",), "inside", ref="s0"),
        TaskPlan("DBMS Revision", STUDY, "DBMS", ("Library", "Exam Preparation"), "clock", ref="s2", offset=45),
        TaskPlan("Project Development", WORK, "Project Development", ("Project Work",), "clock", ref="s4"),
    ),
)

LIBRARY_DAY = Template(
    chains=(
        Chain(
            (
                Slot("s0", "09:00", 150, STUDY, "DSA", LIBRARY, ("Library", "LeetCode", "Exam Preparation"), "study_library"),
                Slot("s1", "11:30", 90, STUDY, "DBMS", LIBRARY, ("Library",), "study_library"),
            )
        ),
        Chain(
            (
                Slot("s2", "15:00", 60, STUDY, "DSA", HOME, ("Home",), "study_home"),
                Slot("s3", "16:00", 60, ENTERTAINMENT, "YouTube", HOME, ("Home",), "watch"),
            )
        ),
        Chain(
            (
                Slot("s4", "19:30", 60, HEALTH, "Gym", GYM, ("Gym", "Evening"), "gym"),
                Slot("s5", "20:30", 75, STUDY, "DBMS", PG, ("PG", "Evening", "Exam Preparation"), "study_pg"),
            )
        ),
    ),
    tasks=(
        TaskPlan("DSA Practice", STUDY, "DSA", ("Library",), "clock", ref="s0"),
        # Planned DSA but the slot actually holds DBMS: category matches,
        # activity differs, tags only partially match.
        TaskPlan("DSA Practice", STUDY, "DSA", ("Library", "Exam Preparation"), "clock", ref="s1"),
        TaskPlan("Gym", HEALTH, "Gym", ("Gym",), "inside", ref="s4"),
        TaskPlan("DBMS Revision", STUDY, "DBMS", ("PG", "Evening"), "clock", ref="s5", offset=45),
    ),
)

BALANCED = Template(
    chains=(
        Chain(
            (
                Slot("s0", "07:00", 40, HEALTH, "Walking", None, ("Morning", "Outdoor"), "walk"),
                Slot("s1", "07:40", 110, STUDY, "DSA", LIBRARY, ("Library", "LeetCode", "Morning"), "study_library"),
                Slot("s2", "09:30", 90, STUDY, "DBMS", COLLEGE, ("College", "Exam Preparation"), "study_college"),
                Slot("s3", "11:00", 30, HEALTH, "Walking", None, ("Morning", "Outdoor"), "walk"),
            )
        ),
        Chain(
            (
                Slot("s4", "13:00", 75, STUDY, "System Design", HOME, ("Home",), "study_home"),
                Slot("s5", "14:15", 45, ENTERTAINMENT, "YouTube", HOME, ("Home",), "watch"),
            )
        ),
        Chain(
            (
                Slot("s6", "18:00", 60, HEALTH, "Gym", GYM, ("Gym", "Evening"), "gym"),
                Slot("s7", "19:00", 90, WORK, "Project Development", PG, ("Project Work", "PG"), "work"),
                Slot("s8", "20:30", 60, ENTERTAINMENT, "Gaming", PG, ("PG", "Evening"), "game"),
            )
        ),
    ),
    tasks=(
        TaskPlan("DSA Practice", STUDY, "DSA", ("Library", "Morning"), "clock", ref="s1"),
        # Starts inside the DSA block, so the two tasks overlap each other.
        TaskPlan("DBMS Revision", STUDY, "DBMS", ("College",), "clock", ref="s2", offset=-30),
        TaskPlan("Gym", HEALTH, "Gym", ("Gym",), "inside", ref="s6"),
    ),
)

PROJECT = Template(
    chains=(
        Chain(
            (
                Slot("s0", "09:30", 180, WORK, "Project Development", PG, ("Project Work", "PG"), "work"),
                Slot("s1", "12:30", 45, ENTERTAINMENT, "YouTube", PG, ("PG",), "watch"),
            )
        ),
        Chain(
            (
                Slot("s2", "16:00", 90, STUDY, "React", HOME, ("Home",), "study_home"),
                Slot("s3", "17:30", 45, HEALTH, "Walking", None, ("Evening", "Outdoor"), "walk"),
            )
        ),
        Chain(
            (
                Slot("s4", "20:00", 60, STUDY, "DSA", PG, ("PG", "LeetCode", "Evening"), "study_pg"),
                Slot("s5", "21:00", 90, ENTERTAINMENT, "Gaming", PG, ("PG", "Evening"), "game"),
            )
        ),
    ),
    tasks=(
        TaskPlan("Project Development", WORK, "Project Development", ("Project Work",), "inside", ref="s0"),
        # Planned in the afternoon gap: no behavior contributes at all.
        TaskPlan("System Design Study", STUDY, "System Design", ("Home", "Evening"), "window", window=("14:00", "15:30")),
        TaskPlan("React Development", STUDY, "React", ("Home", "Evening"), "clock", ref="s2"),
        # Unlabeled task: any Study behavior scores 0.5 (+0.25 on a tag hit).
        TaskPlan("Focus Block", STUDY, None, ("LeetCode",), "clock", ref="s4"),
    ),
)

LIGHT = Template(
    chains=(
        Chain(
            (
                Slot("s0", "10:00", 75, STUDY, "DBMS", HOME, ("Home",), "study_home"),
                Slot("s1", "11:15", 45, ENTERTAINMENT, "YouTube", HOME, ("Home",), "watch"),
            )
        ),
        Chain(
            (
                Slot("s2", "19:00", 60, HEALTH, "Gym", GYM, ("Gym", "Evening"), "gym"),
                Slot("s3", "20:00", 45, STUDY, "DSA", HOME, ("Home", "LeetCode"), "study_home"),
            )
        ),
    ),
    tasks=(
        TaskPlan("DBMS Revision", STUDY, "DBMS", ("Home",), "clock", ref="s0"),
        TaskPlan("Gym", HEALTH, "Gym", ("Gym", "Evening"), "clock", ref="s2"),
        # Slid past the session, so almost none of it overlaps.
        TaskPlan("DSA Practice", STUDY, "DSA", ("Home",), "clock", ref="s3", offset=45),
    ),
)

SPARSE = Template(
    chains=(
        Chain((Slot("s0", "11:00", 120, STUDY, "System Design", HOME, ("Home", "Exam Preparation"), "study_home"),)),
        Chain((Slot("s1", "21:00", 30, ENTERTAINMENT, "YouTube", PG, ("PG", "Evening"), "watch"),)),
    ),
    tasks=(
        TaskPlan("System Design Study", STUDY, "System Design", ("Home",), "clock", ref="s0"),
        TaskPlan("DSA Practice", STUDY, "DSA", ("Library",), "window", window=("14:00", "15:00")),
    ),
)

TEMPLATES = (LIBRARY_DAY, DENSE, BALANCED, PROJECT, LIGHT, SPARSE)

MOODS: dict[str, dict[str, tuple]] = {
    "gym": {
        "energy": (EnergyLevel.High, EnergyLevel.High, EnergyLevel.Medium),
        "focus": (FocusState.Focused, FocusState.Neutral, FocusState.Neutral),
        "emotion": (EmotionState.Calm, EmotionState.Neutral, EmotionState.Neutral),
    },
    "walk": {
        "energy": (EnergyLevel.Medium, EnergyLevel.Low, EnergyLevel.Medium),
        "focus": (FocusState.Neutral, FocusState.Focused),
        "emotion": (EmotionState.Calm, EmotionState.Calm, EmotionState.Neutral),
    },
    "study_library": {
        "energy": (EnergyLevel.High, EnergyLevel.Medium, EnergyLevel.Medium),
        "focus": (FocusState.Focused, FocusState.Focused, FocusState.Neutral),
        "emotion": (EmotionState.Neutral, EmotionState.Calm, EmotionState.Neutral),
    },
    "study_home": {
        "energy": (EnergyLevel.Medium, EnergyLevel.Medium, EnergyLevel.High),
        "focus": (FocusState.Neutral, FocusState.Distracted, FocusState.Focused),
        "emotion": (EmotionState.Neutral, EmotionState.Stressed, EmotionState.Neutral),
    },
    "study_college": {
        "energy": (EnergyLevel.Medium, EnergyLevel.High),
        "focus": (FocusState.Focused, FocusState.Neutral),
        "emotion": (EmotionState.Neutral, EmotionState.Neutral, EmotionState.Stressed),
    },
    "study_pg": {
        "energy": (EnergyLevel.Medium, EnergyLevel.Low, EnergyLevel.Medium),
        "focus": (FocusState.Neutral, FocusState.Focused),
        "emotion": (EmotionState.Calm, EmotionState.Neutral, EmotionState.Stressed),
    },
    "work": {
        "energy": (EnergyLevel.High, EnergyLevel.Medium, EnergyLevel.Medium),
        "focus": (FocusState.Focused, FocusState.Focused, FocusState.Neutral),
        "emotion": (EmotionState.Neutral, EmotionState.Stressed, EmotionState.Neutral),
    },
    "watch": {
        "energy": (EnergyLevel.Medium, EnergyLevel.Low, EnergyLevel.Medium),
        "focus": (FocusState.Distracted, FocusState.Neutral, FocusState.Distracted),
        "emotion": (EmotionState.Calm, EmotionState.Neutral, EmotionState.Neutral),
    },
    "game": {
        "energy": (EnergyLevel.Medium, EnergyLevel.Low),
        "focus": (FocusState.Distracted, FocusState.Distracted, FocusState.Neutral),
        "emotion": (EmotionState.Neutral, EmotionState.Calm, EmotionState.Irritated),
    },
}


def _universe() -> tuple[tuple, tuple]:
    labels: set[tuple] = set()
    tags: set[tuple] = set()
    for template in TEMPLATES:
        for chain in template.chains:
            for slot in chain.slots:
                if slot.label:
                    labels.add((slot.category, slot.label))
                tags.update((slot.category, tag) for tag in slot.tags)
        for plan in template.tasks:
            if plan.label:
                labels.add((plan.category, plan.label))
            tags.update((plan.category, tag) for tag in plan.tags)
    return tuple(sorted(labels)), tuple(sorted(tags))


LABEL_UNIVERSE, TAG_UNIVERSE = _universe()


# --------------------------------------------------------------------------
# Dataset generation
# --------------------------------------------------------------------------


@dataclass
class Session:
    key: str
    start: datetime
    end: datetime
    slot: Slot
    energy: EnergyLevel
    focus: FocusState
    emotion: EmotionState
    precision: Precision


@dataclass
class PlannedTask:
    key: str
    title: str
    category: PrimaryCategory
    label: str | None
    tags: tuple[str, ...]
    start: datetime
    end: datetime
    description: str | None


def seed_id(user_id: uuid.UUID, kind: str, *parts: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, "|".join(str(p) for p in (user_id, kind, *parts)))


def template_for(day: date, today: date, seed: str) -> Template:
    # The two most recent days are always dense so single-day queries for
    # patterns, "summarize my day", and insights have enough to work with.
    if day >= today - timedelta(days=1):
        return DENSE
    offset = int(hashlib.sha256(f"{seed}|template-offset".encode()).hexdigest(), 16)
    return TEMPLATES[(day.toordinal() + offset) % len(TEMPLATES)]


def build_day(
    day: date, template: Template, seed: str, tz: timezone, cutoff: datetime | None
) -> tuple[list[Session], list[PlannedTask]]:
    sessions: list[Session] = []
    for chain_index, chain in enumerate(template.chains):
        chain_rng = random.Random(f"{seed}|{day.isoformat()}|chain|{chain_index}")
        base = datetime.combine(day, time.fromisoformat(chain.slots[0].start), tz)
        cursor = base + timedelta(minutes=chain_rng.choice(CHAIN_JITTER))
        for slot in chain.slots:
            slot_rng = random.Random(f"{seed}|{day.isoformat()}|slot|{slot.key}")
            minutes = max(MIN_SESSION_MINUTES, slot.minutes + slot_rng.choice(DURATION_JITTER))
            mood = MOODS[slot.kind]
            session = Session(
                key=slot.key,
                start=cursor,
                end=cursor + timedelta(minutes=minutes),
                slot=slot,
                energy=slot_rng.choice(mood["energy"]),
                focus=slot_rng.choice(mood["focus"]),
                emotion=slot_rng.choice(mood["emotion"]),
                precision=(
                    Precision.LOW
                    if slot.kind in APPROXIMATE_KINDS and slot_rng.random() < 0.35
                    else Precision.HIGH
                ),
            )
            sessions.append(session)
            cursor = session.end

    if cutoff is not None:
        sessions = _clip_to_cutoff(sessions, cutoff)
    return sessions, _build_tasks(day, template, sessions, tz)


def _clip_to_cutoff(sessions: list[Session], cutoff: datetime) -> list[Session]:
    kept: list[Session] = []
    for session in sessions:
        if session.start >= cutoff:
            continue
        if session.end > cutoff:
            if cutoff - session.start < timedelta(minutes=20):
                continue
            session = replace(session, end=cutoff)
        kept.append(session)
    return kept


def _build_tasks(
    day: date, template: Template, sessions: list[Session], tz: timezone
) -> list[PlannedTask]:
    by_key = {session.key: session for session in sessions}
    slot_by_key = {
        slot.key: slot for chain in template.chains for slot in chain.slots
    }
    tasks: list[PlannedTask] = []
    for index, plan in enumerate(template.tasks):
        window = _task_window(day, plan, by_key, slot_by_key, tz)
        if window is None:
            continue
        start, end = window
        tasks.append(
            PlannedTask(
                key=f"t{index}",
                title=plan.title,
                category=plan.category,
                label=plan.label,
                tags=plan.tags,
                start=start,
                end=end,
                description=plan.description,
            )
        )
    return tasks


def _task_window(
    day: date,
    plan: TaskPlan,
    by_key: dict[str, Session],
    slot_by_key: dict[str, Slot],
    tz: timezone,
) -> tuple[datetime, datetime] | None:
    if plan.strategy == "window":
        return (
            datetime.combine(day, time.fromisoformat(plan.window[0]), tz),
            datetime.combine(day, time.fromisoformat(plan.window[1]), tz),
        )

    if plan.strategy == "inside":
        # Inside the actual (jittered) session, so the overlap covers the whole
        # planned window and the task can reach 100%.
        session = by_key.get(plan.ref)
        if session is None:
            return None
        start = session.start + timedelta(minutes=15)
        end = session.end - timedelta(minutes=15)
        if end - start < timedelta(minutes=20):
            return None
        return start, end

    # clock: the planned window is the template clock time plus an offset, so
    # jitter and duration drift create partial overlaps naturally.
    slot = slot_by_key[plan.ref]
    base_start = datetime.combine(day, time.fromisoformat(slot.start), tz)
    base_end = base_start + timedelta(minutes=slot.minutes)
    offset = timedelta(minutes=plan.offset)
    return base_start + offset, base_end + offset


def build_days(
    today: date, days: int, seed: str, tz: timezone, cutoff: datetime | None
) -> list[tuple[date, list[Session], list[PlannedTask]]]:
    dataset = []
    for ordinal in range(today.toordinal() - days + 1, today.toordinal() + 1):
        day = date.fromordinal(ordinal)
        template = template_for(day, today, seed)
        sessions, tasks = build_day(
            day, template, seed, tz, cutoff if day == today else None
        )
        dataset.append((day, sessions, tasks))
    return dataset


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate(dataset: list[tuple[date, list[Session], list[PlannedTask]]]) -> None:
    labels = set(LABEL_UNIVERSE)
    tags = set(TAG_UNIVERSE)
    errors: list[str] = []

    all_sessions = sorted(
        (session for _, sessions, _ in dataset for session in sessions),
        key=lambda s: s.start,
    )
    latest_end: datetime | None = None
    for session in all_sessions:
        if session.start >= session.end:
            errors.append(f"{session.key}: start_time is not before end_time")
        if latest_end is not None and session.start < latest_end:
            errors.append(
                f"{session.key}: overlaps the previous behavior "
                f"(ends {latest_end:%Y-%m-%d %H:%M}, starts {session.start:%H:%M})"
            )
        latest_end = session.end if latest_end is None else max(latest_end, session.end)

        if session.slot.label and (session.slot.category, session.slot.label) not in labels:
            errors.append(f"{session.key}: label outside the label universe")
        if len(session.slot.tags) != len(set(session.slot.tags)):
            errors.append(f"{session.key}: duplicate context tags")
        for tag in session.slot.tags:
            if (session.slot.category, tag) not in tags:
                errors.append(f"{session.key}: tag '{tag}' does not match its category")

    for day, sessions, tasks in dataset:
        for session in sessions:
            if session.start.date() != day or session.end.date() != day:
                errors.append(f"{session.key}: crosses midnight on {day}")
        for task in tasks:
            if task.start >= task.end:
                errors.append(f"{task.key}: task start is not before end")
            if task.start.date() != day or task.end.date() != day:
                errors.append(f"{task.key}: task crosses midnight on {day}")
            if not 1 <= len(task.title) <= 300:
                errors.append(f"{task.key}: invalid title length")
            if task.label and (task.category, task.label) not in labels:
                errors.append(f"{task.key}: label does not match its category")
            for tag in task.tags:
                if (task.category, tag) not in tags:
                    errors.append(f"{task.key}: tag '{tag}' does not match its category")

    if errors:
        raise SeedError(
            "generated dataset failed validation:\n  " + "\n  ".join(errors[:10])
        )


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------


def _demo_id_sets(user_id: uuid.UUID, today: date) -> tuple[list, list, list, list]:
    days = (
        date.fromordinal(ordinal)
        for ordinal in range(today.toordinal() - RESET_WINDOW_DAYS, today.toordinal() + 1)
    )
    day_keys = [day.isoformat() for day in days]
    behaviors = [
        seed_id(user_id, "behavior", day, key)
        for day in day_keys
        for key in DEMO_BEHAVIOR_KEYS
    ]
    tasks = [
        seed_id(user_id, "task", day, key) for day in day_keys for key in DEMO_TASK_KEYS
    ]
    label_ids = [
        seed_id(user_id, "label", category.value, name) for category, name in LABEL_UNIVERSE
    ]
    tag_ids = [
        seed_id(user_id, "tag", category.value, name) for category, name in TAG_UNIVERSE
    ]
    return behaviors, tasks, label_ids, tag_ids


async def count_existing(
    session: AsyncSession, user_id: uuid.UUID, today: date
) -> dict[str, int]:
    behavior_ids, task_ids, label_ids, tag_ids = _demo_id_sets(user_id, today)

    async def count(model, id_column, ids) -> int:
        return int(
            await session.scalar(
                select(func.count()).where(model.user_id == user_id, id_column.in_(ids))
            )
            or 0
        )

    return {
        "behaviors": await count(Behavior, Behavior.behavior_id, behavior_ids),
        "tasks": await count(Task, Task.task_id, task_ids),
        "activity labels": await count(
            ActivityLabel, ActivityLabel.activity_label_id, label_ids
        ),
        "context tags": await count(BehaviorContextTag, BehaviorContextTag.behavior_context_tag_id, tag_ids),
    }


async def reset_dataset(
    session: AsyncSession, user_id: uuid.UUID, today: date
) -> dict[str, int]:
    behavior_ids, task_ids, label_ids, tag_ids = _demo_id_sets(user_id, today)

    removed_tasks = (
        await session.execute(
            delete(Task).where(Task.user_id == user_id, Task.task_id.in_(task_ids))
        )
    ).rowcount
    removed_behaviors = (
        await session.execute(
            delete(Behavior).where(
                Behavior.user_id == user_id, Behavior.behavior_id.in_(behavior_ids)
            )
        )
    ).rowcount

    # Only remove demo labels/tags that no surviving row still references.
    referenced_labels = set(
        await session.scalars(
            select(Behavior.activity_label_id).where(
                Behavior.activity_label_id.in_(label_ids)
            )
        )
    ) | set(
        await session.scalars(
            select(Task.activity_label_id).where(Task.activity_label_id.in_(label_ids))
        )
    )
    referenced_tags = set(
        await session.scalars(
            select(BehaviorContextTagMap.behavior_context_tag_id).where(
                BehaviorContextTagMap.behavior_context_tag_id.in_(tag_ids)
            )
        )
    ) | set(
        await session.scalars(
            select(TaskContextTagMap.behavior_context_tag_id).where(
                TaskContextTagMap.behavior_context_tag_id.in_(tag_ids)
            )
        )
    )

    removed_labels = 0
    for label_id in label_ids:
        if label_id in referenced_labels:
            continue
        removed_labels += (
            await session.execute(
                delete(ActivityLabel).where(
                    ActivityLabel.user_id == user_id,
                    ActivityLabel.activity_label_id == label_id,
                )
            )
        ).rowcount
    removed_tags = 0
    for tag_id in tag_ids:
        if tag_id in referenced_tags:
            continue
        removed_tags += (
            await session.execute(
                delete(BehaviorContextTag).where(
                    BehaviorContextTag.user_id == user_id,
                    BehaviorContextTag.behavior_context_tag_id == tag_id,
                )
            )
        ).rowcount

    return {
        "behaviors": int(removed_behaviors or 0),
        "tasks": int(removed_tasks or 0),
        "activity labels": int(removed_labels or 0),
        "context tags": int(removed_tags or 0),
    }


async def find_conflicts(
    session: AsyncSession, user_id: uuid.UUID, sessions: list[Session]
) -> list[Behavior]:
    if not sessions:
        return []
    window_start = min(session_.start for session_ in sessions)
    window_end = max(session_.end for session_ in sessions)
    existing = await BehaviorRepository().list_for_range(
        session, user_id, window_start, window_end
    )
    conflicts = [
        behavior
        for behavior in existing
        for session_ in sessions
        if session_.start < behavior.end_time and behavior.start_time < session_.end
    ]
    return sorted(conflicts, key=lambda b: b.start_time)


def _describe(behavior: Behavior) -> str:
    label = behavior.activity_label.activity_label if behavior.activity_label else None
    parts = [
        getattr(behavior.primary_category, "value", behavior.primary_category),
        *([label] if label else []),
    ]
    return (
        f"{' | '.join(parts)} | {behavior.start_time:%Y-%m-%d %H:%M}-"
        f"{behavior.end_time:%H:%M}"
    )


async def insert(
    session: AsyncSession,
    user_id: uuid.UUID,
    dataset: list[tuple[date, list[Session], list[PlannedTask]]],
) -> tuple[dict, dict]:
    activity_labels = {
        (label.primary_category, label.activity_label): label
        for label in await ActivityLabelRepository().list_for_user(session, user_id)
    }
    context_tags = {
        (tag.primary_category, tag.context_tag): tag
        for tag in await ContextTagRepository().list_for_user(session, user_id)
    }

    label_ids: dict[tuple, uuid.UUID] = {}
    labels_created = 0
    for category, name in LABEL_UNIVERSE:
        label = activity_labels.get((category, name))
        if label is None:
            label = ActivityLabel(
                activity_label_id=seed_id(user_id, "label", category.value, name),
                user_id=user_id,
                primary_category=category.value,
                activity_label=name,
            )
            session.add(label)
            labels_created += 1
        label_ids[(category, name)] = label.activity_label_id

    tag_ids: dict[tuple, uuid.UUID] = {}
    tags_created = 0
    for category, name in TAG_UNIVERSE:
        tag = context_tags.get((category, name))
        if tag is None:
            tag = BehaviorContextTag(
                behavior_context_tag_id=seed_id(user_id, "tag", category.value, name),
                user_id=user_id,
                primary_category=category.value,
                context_tag=name,
            )
            session.add(tag)
            context_tags[(category, name)] = tag
            tags_created += 1
        tag_ids[(category, name)] = tag.behavior_context_tag_id

    behaviors: list[Behavior] = []
    tasks: list[Task] = []
    for day, sessions, planned in dataset:
        for session_ in sessions:
            behavior = Behavior(
                behavior_id=seed_id(user_id, "behavior", day.isoformat(), session_.key),
                user_id=user_id,
                start_time=session_.start,
                end_time=session_.end,
                primary_category=session_.slot.category.value,
                activity_label_id=(
                    label_ids.get((session_.slot.category, session_.slot.label))
                    if session_.slot.label
                    else None
                ),
                energy_level=session_.energy.value,
                emotion_state=session_.emotion.value,
                focus_state=session_.focus.value,
                environment=(
                    session_.slot.environment.value
                    if session_.slot.environment
                    else None
                ),
                precision=session_.precision.value,
                source=BehaviorSource.manual.value,
                context_tags=[
                    context_tags[(session_.slot.category, tag)] for tag in session_.slot.tags
                ],
            )
            behaviors.append(behavior)

        for task in planned:
            tasks.append(
                Task(
                    task_id=seed_id(user_id, "task", day.isoformat(), task.key),
                    user_id=user_id,
                    title=task.title,
                    primary_category=task.category.value,
                    activity_label_id=(
                        label_ids.get((task.category, task.label))
                        if task.label
                        else None
                    ),
                    start_time=task.start,
                    end_time=task.end,
                    description=task.description,
                    context_tags=[
                        context_tags[(task.category, tag)] for tag in task.tags
                    ],
                )
            )

    session.add_all(behaviors)
    session.add_all(tasks)
    await session.flush()

    counts = {
        "labels_created": labels_created,
        "labels_reused": len(LABEL_UNIVERSE) - labels_created,
        "tags_created": tags_created,
        "tags_reused": len(TAG_UNIVERSE) - tags_created,
        "behavior_count": len(behaviors),
        "task_count": len(tasks),
        "tracked_minutes": sum(
            int((s.end - s.start).total_seconds() // 60)
            for _, sessions, _ in dataset
            for s in sessions
        ),
    }
    return counts, {
        "behavior_ids": [b.behavior_id for b in behaviors],
        "task_ids": [t.task_id for t in tasks],
    }


# --------------------------------------------------------------------------
# Post-insert verification
# --------------------------------------------------------------------------


async def verify_records(
    session: AsyncSession,
    user_id: uuid.UUID,
    inserted: dict,
) -> None:
    failures: list[str] = []

    behavior_count = int(
        await session.scalar(
            select(func.count()).where(Behavior.behavior_id.in_(inserted["behavior_ids"]))
        )
        or 0
    )
    if behavior_count != len(inserted["behavior_ids"]):
        failures.append(
            f"expected {len(inserted['behavior_ids'])} behaviors, found {behavior_count}"
        )
    task_count = int(
        await session.scalar(
            select(func.count()).where(Task.task_id.in_(inserted["task_ids"]))
        )
        or 0
    )
    if task_count != len(inserted["task_ids"]):
        failures.append(
            f"expected {len(inserted['task_ids'])} tasks, found {task_count}"
        )

    invalid_ranges = int(
        await session.scalar(
            select(func.count()).where(
                Behavior.user_id == user_id,
                Behavior.deleted_at.is_(None),
                Behavior.start_time >= Behavior.end_time,
            )
        )
        or 0
    )
    if invalid_ranges:
        failures.append(f"{invalid_ranges} behaviors with start_time >= end_time")

    left, right = aliased(Behavior), aliased(Behavior)
    overlaps = int(
        await session.scalar(
            select(func.count())
            .select_from(left)
            .join(
                right,
                and_(
                    left.user_id == right.user_id,
                    left.behavior_id < right.behavior_id,
                    left.start_time < right.end_time,
                    right.start_time < left.end_time,
                ),
            )
            .where(
                left.user_id == user_id,
                left.deleted_at.is_(None),
                right.deleted_at.is_(None),
            )
        )
        or 0
    )
    if overlaps:
        failures.append(f"{overlaps} overlapping behavior pairs")

    bad_labels = int(
        await session.scalar(
            select(func.count())
            .select_from(Behavior)
            .join(
                ActivityLabel,
                Behavior.activity_label_id == ActivityLabel.activity_label_id,
            )
            .where(
                Behavior.user_id == user_id,
                Behavior.deleted_at.is_(None),
                or_(
                    ActivityLabel.user_id != Behavior.user_id,
                    ActivityLabel.primary_category != Behavior.primary_category,
                ),
            )
        )
        or 0
    )
    if bad_labels:
        failures.append(f"{bad_labels} behaviors with a mismatched activity label")

    bad_tags = int(
        await session.scalar(
            select(func.count())
            .select_from(BehaviorContextTagMap)
            .join(Behavior, Behavior.behavior_id == BehaviorContextTagMap.behavior_id)
            .join(
                BehaviorContextTag,
                BehaviorContextTag.behavior_context_tag_id
                == BehaviorContextTagMap.behavior_context_tag_id,
            )
            .where(
                Behavior.user_id == user_id,
                or_(
                    BehaviorContextTag.user_id != Behavior.user_id,
                    BehaviorContextTag.primary_category != Behavior.primary_category,
                ),
            )
        )
        or 0
    )
    if bad_tags:
        failures.append(f"{bad_tags} behavior-context mappings in the wrong category")

    bad_task_labels = int(
        await session.scalar(
            select(func.count())
            .select_from(Task)
            .join(ActivityLabel, Task.activity_label_id == ActivityLabel.activity_label_id)
            .where(
                Task.user_id == user_id,
                or_(
                    ActivityLabel.user_id != Task.user_id,
                    ActivityLabel.primary_category != Task.primary_category,
                ),
            )
        )
        or 0
    )
    if bad_task_labels:
        failures.append(f"{bad_task_labels} tasks with a mismatched activity label")

    bad_task_tags = int(
        await session.scalar(
            select(func.count())
            .select_from(TaskContextTagMap)
            .join(Task, Task.task_id == TaskContextTagMap.task_id)
            .join(
                BehaviorContextTag,
                BehaviorContextTag.behavior_context_tag_id
                == TaskContextTagMap.behavior_context_tag_id,
            )
            .where(
                Task.user_id == user_id,
                or_(
                    BehaviorContextTag.user_id != Task.user_id,
                    BehaviorContextTag.primary_category != Task.primary_category,
                ),
            )
        )
        or 0
    )
    if bad_task_tags:
        failures.append(f"{bad_task_tags} task-context mappings in the wrong category")

    invalid_tasks = int(
        await session.scalar(
            select(func.count()).where(
                Task.user_id == user_id, Task.start_time >= Task.end_time
            )
        )
        or 0
    )
    if invalid_tasks:
        failures.append(f"{invalid_tasks} tasks with start_time >= end_time")

    if failures:
        raise SeedError(
            "seeded data failed invariant checks:\n  " + "\n  ".join(failures)
        )


async def verify_engines(
    session: AsyncSession,
    user_id: uuid.UUID,
    today: date,
    days: int,
    tz_offset: int,
) -> dict:
    settings = get_settings()
    behaviors = BehaviorRepository()
    tasks = TaskRepository()
    task_analysis = TaskAnalysisService(tasks, behaviors)
    analytics = AnalyticsService(behaviors, task_analysis)
    patterns = PatternDetectionService(
        behaviors,
        min_transition_count=settings.PATTERN_MIN_TRANSITION_COUNT,
        min_context_sessions=settings.PATTERN_MIN_CONTEXT_SESSIONS,
    )

    failures: list[str] = []
    yesterday = today - timedelta(days=1)
    daily = await analytics.daily(session, user_id, yesterday, tz_offset)
    if daily.summary.tracked_minutes <= 0 or not daily.categories:
        failures.append("daily analytics returned no tracked time for yesterday")

    analyses = await task_analysis.analyze_many_for_user(session, user_id)
    rates = [analysis.completion_rate for analysis in analyses]
    if not analyses:
        failures.append("task analysis returned no tasks")
    else:
        if not any(rate == 100 for rate in rates):
            failures.append("no task reaches 100% completion")
        if not any(0 < rate < 100 for rate in rates):
            failures.append("no task has a partial completion rate")
        if min(rates) >= 100:
            failures.append("every task is at 100% completion")

    range_start = today - timedelta(days=days - 1)
    transitions = await patterns.transitions(
        session, user_id, range_start, today, tz_offset
    )
    if not transitions.category_transitions:
        failures.append("pattern detection found no category transitions")
    if not transitions.activity_transitions:
        failures.append("pattern detection found no activity transitions")

    context_patterns = await patterns.context(
        session, user_id, range_start, today, tz_offset
    )
    if not context_patterns.context_stats:
        failures.append("context analysis found no context buckets")
    if not context_patterns.associations:
        failures.append("context analysis found no associations")

    builder = AIContextBuilder(analytics, task_analysis, tasks, patterns)
    chat_context = await builder.build(session, user_id, yesterday, tz_offset)
    rendered = render_chat_context(chat_context)
    if "<life_tracker_context>" not in rendered or "Tracked:" not in rendered:
        failures.append("chat context rendering produced no usable output")

    if failures:
        raise SeedError(
            "engine verification failed:\n  " + "\n  ".join(failures)
        )

    totals = TaskAnalysisService.summarize(analyses)
    top_category = max(daily.categories, key=lambda c: c.duration_minutes)
    return {
        "analyzed_tasks": len(analyses),
        "verify_day": yesterday.isoformat(),
        "tracked": daily.summary.tracked_minutes,
        "unaccounted": daily.summary.unaccounted_minutes,
        "top_category": getattr(top_category.category, "value", top_category.category),
        "top_category_minutes": top_category.duration_minutes,
        "min_rate": min(rates),
        "avg_rate": totals.completion_rate,
        "max_rate": max(rates),
        "category_transitions": len(transitions.category_transitions),
        "activity_transitions": len(transitions.activity_transitions),
        "associations": len(context_patterns.associations),
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def resolve_tz(offset_minutes: int | None) -> tuple[timezone, int]:
    if offset_minutes is not None:
        return timezone(timedelta(minutes=offset_minutes)), offset_minutes
    now = datetime.now().astimezone()
    offset = now.utcoffset() or timedelta(0)
    return timezone(offset), int(offset.total_seconds() // 60)


async def run(args: argparse.Namespace) -> dict:
    tz, tz_offset = resolve_tz(args.tz_offset_minutes)
    now = datetime.now(tz)
    today = now.date()
    # No behavior may start after the current hour, so the demo never shows
    # future time on the day it is seeded.
    cutoff = now.replace(minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_clerk_user_id(args.clerk_user_id)
        if user is None:
            raise SeedError(
                f"no application user exists for Clerk id '{args.clerk_user_id}'; "
                "the user must sign in once so the Clerk webhook creates the row"
            )

        existing = await count_existing(session, user.id, today)
        if any(existing.values()):
            if not args.reset:
                found = ", ".join(
                    f"{count} {name}" for name, count in existing.items() if count
                )
                raise SeedError(
                    f"demo data already exists for this user ({found}); "
                    "rerun with --reset to replace it"
                )
            removed = await reset_dataset(session, user.id, today)
        else:
            removed = None

        dataset = build_days(today, args.days, args.seed, tz, cutoff)
        validate(dataset)
        sessions = [s for _, day_sessions, _ in dataset for s in day_sessions]

        conflicts = await find_conflicts(session, user.id, sessions)
        if conflicts:
            shown = "; ".join(_describe(behavior) for behavior in conflicts[:5])
            raise SeedError(
                f"{len(conflicts)} existing behaviors overlap the demo schedule "
                f"and would violate the no-overlap rule: {shown}"
            )

        try:
            counts, inserted = await insert(session, user.id, dataset)
            await verify_records(session, user.id, inserted)
            engine = await verify_engines(session, user.id, today, args.days, tz_offset)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise SeedError(
                f"the database rejected the generated dataset: {exc.orig}"
            ) from exc
        except Exception:
            await session.rollback()
            raise

    return {
        "clerk_user_id": user.clerk_user_id,
        "user_name": user.first_name or user.email or "unknown",
        "removed": removed,
        "range_start": dataset[0][0].isoformat(),
        "range_end": dataset[-1][0].isoformat(),
        "days": args.days,
        "tz_offset": tz_offset,
        **counts,
        **engine,
    }


def print_summary(stats: dict) -> None:
    print()
    if stats.get("removed") and any(stats["removed"].values()):
        print(
            "Removed previous demo data: "
            + ", ".join(f"{count} {name}" for name, count in stats["removed"].items())
        )
        print()
    print("Demo data seeded successfully.")
    print()
    print(f"User:            {stats['user_name']} ({stats['clerk_user_id']})")
    print(
        f"Date range:      {stats['range_start']} to {stats['range_end']} "
        f"({stats['days']} days, tz offset {stats['tz_offset']:+d} min)"
    )
    print(
        f"Activity labels: {stats['labels_created']} created, "
        f"{stats['labels_reused']} reused"
    )
    print(
        f"Context tags:    {stats['tags_created']} created, "
        f"{stats['tags_reused']} reused"
    )
    print(
        f"Behaviors:       {stats['behavior_count']} "
        f"({stats['tracked_minutes']:,} tracked minutes)"
    )
    print(f"Tasks:           {stats['task_count']}")
    print()
    print("Verification:")
    print("  invariants:      no overlaps; label, tag, and ownership checks passed")
    print(
        f"  analytics {stats['verify_day']}: tracked {stats['tracked']} min, "
        f"unaccounted {stats['unaccounted']} min, top category "
        f"{stats['top_category']} ({stats['top_category_minutes']} min)"
    )
    print(
        f"  task analysis:   {stats['analyzed_tasks']} tasks, completion min "
        f"{stats['min_rate']}% / avg {stats['avg_rate']}% / max {stats['max_rate']}%"
    )
    print(
        f"  patterns:        {stats['category_transitions']} category transitions, "
        f"{stats['activity_transitions']} activity transitions, "
        f"{stats['associations']} context associations "
        f"({stats['days']}-day window)"
    )
    print(
        "  chat context:    rendered the verified <life_tracker_context> block "
        f"for {stats['verify_day']}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed deterministic demo data for one existing user."
    )
    parser.add_argument(
        "--clerk-user-id",
        required=True,
        help="Clerk user id of the existing application user to seed",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove data previously created by this script, then recreate it",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"days of history ending today (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--seed",
        default=DEFAULT_SEED,
        help="randomness seed; same seed and days produce the same dataset",
    )
    parser.add_argument(
        "--tz-offset-minutes",
        type=int,
        default=None,
        help="UTC offset used to place clock times (default: local time)",
    )
    args = parser.parse_args(argv)
    if not MIN_DAYS <= args.days <= MAX_DAYS:
        parser.error(f"--days must be between {MIN_DAYS} and {MAX_DAYS}")
    if args.tz_offset_minutes is not None and not -840 <= args.tz_offset_minutes <= 840:
        parser.error("--tz-offset-minutes must be between -840 and 840")
    return args


def main() -> int:
    args = parse_args()
    try:
        stats = asyncio.run(run(args), loop_factory=loop_factory)
    except SeedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
