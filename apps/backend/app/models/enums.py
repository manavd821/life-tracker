from enum import Enum

from sqlalchemy import Enum as PgEnum


class PrimaryCategory(str, Enum):
    Entertainment = "Entertainment"
    Study = "Study"
    Health = "Health"
    Work = "Work"
    Travel = "Travel"
    Social = "Social"
    Rest = "Rest"
    Admin = "Admin"


class EnergyLevel(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class EmotionState(str, Enum):
    Calm = "Calm"
    Stressed = "Stressed"
    Neutral = "Neutral"
    Irritated = "Irritated"


class FocusState(str, Enum):
    Focused = "Focused"
    Neutral = "Neutral"
    Distracted = "Distracted"


class Environment(str, Enum):
    Home = "Home"
    College = "College"
    Library = "Library"
    PG = "PG"
    Travel = "Travel"
    Gym = "Gym"
    Office = "Office"


class Precision(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"


class BehaviorSource(str, Enum):
    manual = "manual"
    live_tracking = "live_tracking"
    gap_fill = "gap_fill"
    edit = "edit"
    from_task = "from_task"


def _values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


PRIMARY_CATEGORY = PgEnum(
    PrimaryCategory, name="primary_category", values_callable=_values
)
ENERGY_LEVEL = PgEnum(EnergyLevel, name="energy_level", values_callable=_values)
EMOTION_STATE = PgEnum(EmotionState, name="emotion_state", values_callable=_values)
FOCUS_STATE = PgEnum(FocusState, name="focus_state", values_callable=_values)
ENVIRONMENT = PgEnum(Environment, name="environment", values_callable=_values)
PRECISION = PgEnum(Precision, name="behavior_precision", values_callable=_values)
BEHAVIOR_SOURCE = PgEnum(BehaviorSource, name="behavior_source", values_callable=_values)
