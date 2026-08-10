from app.optimizer.types import MarketStrength, ProjectedCalendarPoint, SeasonCalendar


def market_strength(season_week: int | None) -> MarketStrength:
    if season_week is None:
        return MarketStrength.UNKNOWN
    if season_week in (1, 2, 3, 4):
        return MarketStrength.VERY_STRONG
    if season_week in (5, 6, 7, 15, 16):
        return MarketStrength.STRONG
    if season_week in (8, 9, 10):
        return MarketStrength.NORMAL
    if season_week in (11, 12, 13, 14):
        return MarketStrength.VERY_WEAK
    raise ValueError("Hattrick season week must be 1 to 16")


def _advance(calendar: SeasonCalendar, optimizer_week: int) -> tuple[int | None, int | None]:
    if calendar.current_season_week is None:
        return calendar.current_season_number, None
    zero_based = calendar.current_season_week - 1 + optimizer_week
    season_week = zero_based % 16 + 1
    season_number = (
        calendar.current_season_number + zero_based // 16
        if calendar.current_season_number is not None
        else None
    )
    return season_number, season_week


def calendar_point(calendar: SeasonCalendar, optimizer_week: int) -> ProjectedCalendarPoint:
    season_number, season_week = _advance(calendar, optimizer_week)
    strength = market_strength(season_week)
    weeks_until_stronger: int | None = None
    if season_week is not None:
        order = {
            MarketStrength.VERY_WEAK: 0,
            MarketStrength.WEAK: 1,
            MarketStrength.NORMAL: 2,
            MarketStrength.STRONG: 3,
            MarketStrength.VERY_STRONG: 4,
            MarketStrength.UNKNOWN: -1,
        }
        for offset in range(1, 17):
            _, candidate_week = _advance(calendar, optimizer_week + offset)
            if order[market_strength(candidate_week)] > order[strength]:
                weeks_until_stronger = offset
                break
    return ProjectedCalendarPoint(
        optimizer_week=optimizer_week,
        season_number=season_number,
        season_week=season_week,
        market_strength=strength,
        weeks_until_stronger_window=weeks_until_stronger,
    )
