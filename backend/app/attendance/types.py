from dataclasses import dataclass
from enum import StrEnum


class SeatCategory(StrEnum):
    TERRACES = "terraces"
    BASIC = "basic"
    ROOF = "roof"
    VIP = "vip"


class Weather(StrEnum):
    RAIN = "rain"
    OVERCAST = "overcast"
    PARTLY_CLOUDY = "partly_cloudy"
    SUNNY = "sunny"


@dataclass(frozen=True, slots=True)
class SeatCounts:
    terraces: int
    basic: int
    roof: int
    vip: int

    def value(self, category: SeatCategory) -> int:
        return int(getattr(self, category.value))


@dataclass(frozen=True, slots=True)
class AttendanceRequest:
    fan_count: int
    fan_mood: int
    weather: Weather
    capacity: SeatCounts
    match_type: int
    is_home: bool


@dataclass(frozen=True, slots=True)
class SectionEstimate:
    category: SeatCategory
    baseline_demand: float
    adjusted_demand: float
    capacity: int
    sold: int
    unmet_demand: float
    utilization: float
    ticket_price: float
    weekly_maintenance_per_seat: float
    gross_revenue: float
    unmet_revenue_potential: float


@dataclass(frozen=True, slots=True)
class AttendanceEstimate:
    model_version: str
    quality: str
    sections: tuple[SectionEstimate, ...]
    baseline_total_demand: float
    adjusted_total_demand: float
    total_capacity: int
    total_attendance: int
    utilization: float
    gross_revenue: float
    average_revenue_per_spectator: float
    club_revenue: int | None
    opponent_revenue: int | None
    revenue_share: float | None
    notes: tuple[str, ...]


class UnsupportedFanMood(ValueError):
    pass
