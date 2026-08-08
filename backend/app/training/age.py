from dataclasses import dataclass

HATTRICK_DAYS_PER_YEAR = 112
HATTRICK_DAYS_PER_WEEK = 7


@dataclass(frozen=True, slots=True)
class HattrickAge:
    years: int
    days: int

    def __post_init__(self) -> None:
        if self.years < 0:
            raise ValueError("Hattrick age years must be non-negative")
        if not 0 <= self.days < HATTRICK_DAYS_PER_YEAR:
            raise ValueError("Hattrick age days must be in [0, 111]")

    @property
    def fractional_years(self) -> float:
        return self.years + self.days / HATTRICK_DAYS_PER_YEAR

    def advance_days(self, days: int) -> "HattrickAge":
        if days < 0:
            raise ValueError("Age advancement must be non-negative")
        total_days = self.years * HATTRICK_DAYS_PER_YEAR + self.days + days
        years, age_days = divmod(total_days, HATTRICK_DAYS_PER_YEAR)
        return HattrickAge(years=years, days=age_days)

    def advance_week(self) -> "HattrickAge":
        return self.advance_days(HATTRICK_DAYS_PER_WEEK)
