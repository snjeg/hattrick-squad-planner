from app.attendance.types import SeatCategory, Weather

MODEL_VERSION = "community-arena-table-2026-08-09-v1"
MODEL_QUALITY = "approximate-low-confidence"

# Hattrick Wiki community arena-sizing research, not an official attendance formula.
# Values are unconstrained demand per fan-club member by supporter mood (1..11).
DEMAND_PER_FAN: dict[int, dict[SeatCategory, float]] = {
    1: {SeatCategory.TERRACES: 7.852, SeatCategory.BASIC: 2.341, SeatCategory.ROOF: 1.234, SeatCategory.VIP: .104},
    2: {SeatCategory.TERRACES: 8.415, SeatCategory.BASIC: 2.729, SeatCategory.ROOF: 1.768, SeatCategory.VIP: .179},
    3: {SeatCategory.TERRACES: 9.087, SeatCategory.BASIC: 3.097, SeatCategory.ROOF: 2.213, SeatCategory.VIP: .240},
    4: {SeatCategory.TERRACES: 9.797, SeatCategory.BASIC: 3.457, SeatCategory.ROOF: 2.628, SeatCategory.VIP: .297},
    5: {SeatCategory.TERRACES: 10.52, SeatCategory.BASIC: 3.814, SeatCategory.ROOF: 3.034, SeatCategory.VIP: .352},
    6: {SeatCategory.TERRACES: 11.26, SeatCategory.BASIC: 4.170, SeatCategory.ROOF: 3.437, SeatCategory.VIP: .406},
    7: {SeatCategory.TERRACES: 12.00, SeatCategory.BASIC: 4.526, SeatCategory.ROOF: 3.841, SeatCategory.VIP: .460},
    8: {SeatCategory.TERRACES: 12.74, SeatCategory.BASIC: 4.882, SeatCategory.ROOF: 4.247, SeatCategory.VIP: .514},
    9: {SeatCategory.TERRACES: 13.49, SeatCategory.BASIC: 5.238, SeatCategory.ROOF: 4.657, SeatCategory.VIP: .568},
    10: {SeatCategory.TERRACES: 14.23, SeatCategory.BASIC: 5.594, SeatCategory.ROOF: 5.069, SeatCategory.VIP: .623},
    11: {SeatCategory.TERRACES: 14.98, SeatCategory.BASIC: 5.951, SeatCategory.ROOF: 5.485, SeatCategory.VIP: .678},
}
# Current official Manual euro-equivalent values. Currency conversion is a later concern.
TICKET_PRICES = {SeatCategory.TERRACES: 6.5, SeatCategory.BASIC: 9.5, SeatCategory.ROOF: 18.0, SeatCategory.VIP: 32.5}
WEEKLY_MAINTENANCE = {SeatCategory.TERRACES: .5, SeatCategory.BASIC: .7, SeatCategory.ROOF: 1.0, SeatCategory.VIP: 2.5}

# Editorial, versioned assumptions preserving the documented directional effects.
# Hattrick does not publish exact weather multipliers.
WEATHER_MODIFIERS = {
    Weather.SUNNY: {SeatCategory.TERRACES: 1.05, SeatCategory.BASIC: 1.03, SeatCategory.ROOF: .98, SeatCategory.VIP: 1.0},
    Weather.PARTLY_CLOUDY: {category: 1.0 for category in SeatCategory},
    Weather.OVERCAST: {SeatCategory.TERRACES: .95, SeatCategory.BASIC: .98, SeatCategory.ROOF: 1.05, SeatCategory.VIP: 1.0},
    Weather.RAIN: {SeatCategory.TERRACES: .85, SeatCategory.BASIC: .90, SeatCategory.ROOF: 1.15, SeatCategory.VIP: 1.02},
}
