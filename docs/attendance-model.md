# Attendance and match-revenue model

Milestone 4.1 provides a reusable, table-driven estimate. It is deliberately labeled
`approximate-low-confidence`: Hattrick does not publish an exact attendance formula, and
precise calculator output is not evidence that such a formula is known.

## Inputs and factual boundary

The economy CHPP response supplies `FanClubSize` and `SupportersPopularity`. They are
normalized as `supporter_count` and `fan_mood` on the append-only finance snapshot, so an
existing plan continues to use the supporter facts from its starting sync. Arena section
capacities and fixture match types are also frozen to that sync. A user may override fan
mood for a scenario without changing imported facts.

## Demand table

`backend/app/attendance/tables.py` transcribes the eleven mood rows in the Hattrick Wiki
community arena research (furious through sending love poems). Each row gives demand per
fan-club member for terraces, basic seating, roof seating, and VIP. The source describes
an arena-sizing/profitability study, not an official per-match predictor; using it as an
unconstrained demand baseline is therefore an explicit modeling assumption. The source
has no coefficient for mood 0, so the engine returns unsupported instead of extrapolating.

For every section:

`baseline = supporter_count × mood_coefficient`

`weather_adjusted = baseline × weather_modifier`

`sold = min(round(weather_adjusted), section_capacity)`

Demand that exceeds one section is reported as unmet demand and is never moved to another
section. This matches the official rule that a supporter unable to buy the desired class
does not substitute another class. Each section also exposes utilization, ticket price,
weekly maintenance per seat, and gross unmet-revenue potential as reusable inputs for a
future stadium analyzer; this milestone makes no build recommendation.

## Weather

The four game weather states are rain, overcast, partly cloudy, and sunny. Official text
only gives directional behavior: rain reduces attendance and favors covered places; good
weather favors uncovered places. The versioned multipliers in `tables.py` are conservative
editorial assumptions, not recovered coefficients. When weather is unknown, the API
returns all four scenarios and finance does not pick an average or pretend one is known.

## Revenue and maintenance

Current official Manual euro-equivalent ticket prices are 6.5, 9.5, 18, and 32.5 by seat
class; weekly maintenance is 0.5, 0.7, 1, and 2.5. Revenue sharing is mapped separately:

- league: home club 100%;
- national cup: home 2/3 and away 1/3;
- qualifiers and supported friendlies: 50/50;
- other match types: unsupported rather than guessed.

The older community Arena page displays different ticket values. The official Manual is
used because it is the stronger current source. Prices are presently interpreted in the
app's base money unit; multi-currency conversion is not modeled.

## Finance integration

Each fixture resolves club revenue in this order:

1. manual per-fixture club-revenue override;
2. attendance estimate, only for a home fixture with complete snapshot facts and explicit
   weather;
3. legacy expected-home-match-revenue assumption;
4. zero, with a source label.

The domain supports away revenue shares. The current service cannot estimate an away gate
because the plan snapshot does not contain the host's supporter and arena inputs; a manual
override can represent known cup or friendly income. Weekly finance rows expose contributing
fixture IDs and the source used for every fixture.

## Traceability and exclusions

Sources audited 2026-08-09:

- [Hattrick Wiki Manual](https://wiki.hattrick.org/wiki/Manual): official ticket prices, maintenance, attendance direction, no
  substitution, and sharing rules;
- [Hattrick Wiki Attendance/Arena research](https://wiki.hattrick.org/wiki/Attendance): the eleven community seat-demand rows;
- [Hattrick Wiki Weather](https://wiki.hattrick.org/wiki/Weather): four game weather states;
- [CHPP economy](https://wiki.hattrick.org/wiki/CHPP_Development/XML/economy) and
  [match-details](https://wiki.hattrick.org/wiki/CHPP_Development/XML/matchDetails)
  documentation plus the current open-source Go CHPP model:
  supporter facts, match types, weather IDs, and post-match sold-seat fields;
- [NRG arena tool](https://nrgjack.altervista.org/tools/eco): reviewed but intentionally not used as a match predictor. Its current
  output is an arena-sizing compromise derived from DAC/Brun heuristics and oversized-arena
  assumptions, not a documented per-fixture attendance formula.

Opponent league position, derby/cup attractiveness, season progression, and opponent fan
base are omitted because the researched sources do not provide credible reusable
coefficients. Historical `matchdetails` imports would be the next calibration extension,
but adding those calls and storage is outside this milestone. Stadium expansion advice and
optimization are also outside scope.
