from decimal import ROUND_HALF_UP, Decimal

from app.attendance.sharing import revenue_share
from app.attendance.tables import (
    DEMAND_PER_FAN,
    MODEL_QUALITY,
    MODEL_VERSION,
    TICKET_PRICES,
    WEATHER_MODIFIERS,
    WEEKLY_MAINTENANCE,
)
from app.attendance.types import (
    AttendanceEstimate,
    AttendanceRequest,
    SectionEstimate,
    UnsupportedFanMood,
    Weather,
)


def estimate_attendance(request: AttendanceRequest) -> AttendanceEstimate:
    if request.fan_count < 0:
        raise ValueError("Fan count cannot be negative")
    if any(request.capacity.value(category) < 0 for category in TICKET_PRICES):
        raise ValueError("Seat capacity cannot be negative")
    try:
        mood_table = DEMAND_PER_FAN[request.fan_mood]
    except KeyError as exc:
        raise UnsupportedFanMood(
            "No sourced community coefficient exists for this fan mood"
        ) from exc
    sections: list[SectionEstimate] = []
    for category, price in TICKET_PRICES.items():
        baseline = request.fan_count * mood_table[category]
        adjusted = baseline * WEATHER_MODIFIERS[request.weather][category]
        capacity = request.capacity.value(category)
        sold = min(capacity, max(0, round(adjusted)))
        sections.append(
            SectionEstimate(
                category,
                baseline,
                adjusted,
                capacity,
                sold,
                max(0.0, adjusted - capacity),
                sold / capacity if capacity else 0.0,
                price,
                WEEKLY_MAINTENANCE[category],
                sold * price,
                max(0.0, adjusted - capacity) * price,
            )
        )
    gross = sum(section.gross_revenue for section in sections)
    share = revenue_share(request.match_type, is_home=request.is_home)
    club = (
        None
        if share is None
        else int(
            (Decimal(str(gross)) * Decimal(str(share))).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    )
    opponent = (
        None
        if club is None
        else int(Decimal(str(gross)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) - club
    )
    notes: tuple[str, ...] = (
        "Community arena-sizing table used as an approximate demand baseline.",
        "Weather modifiers are explicit editorial assumptions, not an official formula.",
    )
    if share is None:
        notes += ("Revenue sharing is unsupported for this match type.",)
    baseline_total = sum(section.baseline_demand for section in sections)
    adjusted_total = sum(section.adjusted_demand for section in sections)
    total_capacity = sum(section.capacity for section in sections)
    total_attendance = sum(section.sold for section in sections)
    return AttendanceEstimate(
        MODEL_VERSION,
        MODEL_QUALITY,
        tuple(sections),
        baseline_total,
        adjusted_total,
        total_capacity,
        total_attendance,
        total_attendance / total_capacity if total_capacity else 0.0,
        gross,
        gross / total_attendance if total_attendance else 0.0,
        club,
        opponent,
        share,
        notes,
    )


def weather_scenarios(request: AttendanceRequest) -> dict[Weather, AttendanceEstimate]:
    return {
        weather: estimate_attendance(
            AttendanceRequest(
                request.fan_count,
                request.fan_mood,
                weather,
                request.capacity,
                request.match_type,
                request.is_home,
            )
        )
        for weather in Weather
    }
