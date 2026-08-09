import pytest

from app.attendance.engine import estimate_attendance, weather_scenarios
from app.attendance.sharing import revenue_share
from app.attendance.tables import DEMAND_PER_FAN, TICKET_PRICES, WEEKLY_MAINTENANCE
from app.attendance.types import AttendanceRequest, SeatCategory, SeatCounts, UnsupportedFanMood, Weather


CAPACITY = SeatCounts(20_000, 8_000, 6_000, 1_000)


def request(**changes: object) -> AttendanceRequest:
    values: dict[str, object] = {
        "fan_count": 1_000,
        "fan_mood": 7,
        "weather": Weather.PARTLY_CLOUDY,
        "capacity": CAPACITY,
        "match_type": 1,
        "is_home": True,
    }
    values.update(changes)
    return AttendanceRequest(**values)  # type: ignore[arg-type]


def test_golden_community_table_satisfied_mood() -> None:
    result = estimate_attendance(request())
    assert [section.baseline_demand for section in result.sections] == pytest.approx(
        [12_000, 4_526, 3_841, 460]
    )
    assert result.total_attendance == 20_827
    assert result.baseline_total_demand == pytest.approx(20_827)
    assert result.average_revenue_per_spectator == pytest.approx(
        result.gross_revenue / result.total_attendance
    )


@pytest.mark.parametrize("mood", range(1, 12))
def test_every_sourced_mood_has_all_seat_coefficients(mood: int) -> None:
    assert set(DEMAND_PER_FAN[mood]) == set(SeatCategory)


def test_mood_increases_unconstrained_demand() -> None:
    assert estimate_attendance(request(fan_mood=8)).total_attendance > estimate_attendance(
        request(fan_mood=6)
    ).total_attendance


def test_rain_reduces_total_and_shifts_share_to_covered_seats() -> None:
    neutral = estimate_attendance(request(weather=Weather.PARTLY_CLOUDY))
    rain = estimate_attendance(request(weather=Weather.RAIN))
    assert rain.total_attendance < neutral.total_attendance
    neutral_roof = neutral.sections[2].sold / neutral.total_attendance
    rain_roof = rain.sections[2].sold / rain.total_attendance
    assert rain_roof > neutral_roof


def test_capacity_caps_each_section_without_redistribution() -> None:
    result = estimate_attendance(request(capacity=SeatCounts(100, 8_000, 6_000, 1_000)))
    terraces = result.sections[0]
    assert terraces.sold == 100
    assert terraces.unmet_demand == pytest.approx(11_900)
    assert terraces.unmet_revenue_potential == pytest.approx(11_900 * 6.5)
    assert result.sections[1].sold == 4_526


def test_zero_capacity_is_valid() -> None:
    result = estimate_attendance(request(capacity=SeatCounts(0, 0, 0, 0)))
    assert result.total_attendance == 0
    assert all(section.utilization == 0 for section in result.sections)


def test_section_and_gross_revenue_use_official_prices() -> None:
    result = estimate_attendance(request(fan_count=1, fan_mood=1))
    assert result.gross_revenue == sum(section.gross_revenue for section in result.sections)
    assert TICKET_PRICES[SeatCategory.VIP] == 32.5
    assert WEEKLY_MAINTENANCE[SeatCategory.VIP] == 2.5


@pytest.mark.parametrize(
    ("match_type", "is_home", "expected"),
    [(1, True, 1.0), (1, False, 0.0), (3, True, 2 / 3), (3, False, 1 / 3), (2, True, .5), (4, False, .5), (5, False, .5)],
)
def test_revenue_sharing(match_type: int, is_home: bool, expected: float) -> None:
    assert revenue_share(match_type, is_home=is_home) == pytest.approx(expected)


def test_unknown_match_type_is_explicitly_unsupported() -> None:
    result = estimate_attendance(request(match_type=99))
    assert result.club_revenue is None
    assert result.revenue_share is None


def test_unknown_weather_is_represented_as_four_scenarios() -> None:
    scenarios = weather_scenarios(request())
    assert set(scenarios) == set(Weather)
    assert len({item.total_attendance for item in scenarios.values()}) > 1


def test_estimate_is_deterministic() -> None:
    assert estimate_attendance(request()) == estimate_attendance(request())


@pytest.mark.parametrize(
    "bad_request",
    [request(fan_count=-1), request(capacity=SeatCounts(-1, 0, 0, 0))],
)
def test_negative_inputs_are_rejected(bad_request: AttendanceRequest) -> None:
    with pytest.raises(ValueError):
        estimate_attendance(bad_request)


@pytest.mark.parametrize("mood", [0, 12])
def test_unsourced_moods_are_not_extrapolated(mood: int) -> None:
    with pytest.raises(UnsupportedFanMood):
        estimate_attendance(request(fan_mood=mood))
