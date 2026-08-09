# Plan-bound finance projection

## Facts, assumptions, and projections

Every finance value has one of three meanings:

- **Current fact:** imported from CHPP and stored append-only with a sync run.
- **Assumption:** explicitly entered by the manager for a named scenario.
- **Projection:** calculated from plan-bound facts, assumptions, fixtures, and estimated
  wages. It never overwrites factual snapshots.

Creating a training plan binds the finance snapshot from the same completed sync as its
player snapshots. Later syncs append newer economy, arena, and fixture facts but do not
change an existing plan.

## CHPP inputs

The sync adapter uses the documented current XML interfaces:

- [`economy` 1.3](https://wiki.hattrick.org/wiki/CHPP_Development/XML/economy): cash,
  expected cash, sponsor/spectator/financial/temporary income and arena/player/financial/
  temporary/staff/youth costs for the current week.
- [`arenaDetails` 1.2](https://wiki.hattrick.org/wiki/CHPP_Development/XML/arenaDetails):
  arena identity and current terrace/basic/roof/VIP capacity.
- [`matches` 2.2](https://wiki.hattrick.org/wiki/CHPP_Development/XML/matches): dated
  upcoming fixtures, match type, opponents, and home/away identity.

Only straightforward normalized values are persisted. Historical observations remain
append-only in `finance_snapshots`, `arena_snapshots`, and `fixture_snapshots`.

## Weekly cash-flow model

For each plan week:

```text
operating cash flow = sponsor income
                    + resolved club revenue for each known fixture
                    - projected squad wages
                    - fixed staff, youth, and arena costs

capital cash flow = 0
ending cash = prior cash + operating cash flow + capital cash flow
```

Player purchases, sales, transfer recommendations, and transfer values are excluded.
Keeping capital cash flow explicit prevents operating sustainability from being confused
with transfer proceeds. Block checkpoints show cash and weekly wage burden at each block
end; the API also returns every weekly row.

## Explicit assumptions

Current cash, sponsor income, staff, youth, and arena costs default from the plan-bound
finance snapshot and can be overridden. Fixture revenue resolves by manual per-fixture
override, then a weather-specific attendance estimate for eligible home fixtures, then
the legacy expected-home-revenue assumption, then zero. Unknown weather remains four
visible scenarios and is not averaged into finance. Away cup/friendly shares are supported
by the revenue domain; the current service needs a manual override because it does not
import the host club's arena and supporter inputs. See `docs/attendance-model.md`.

The current sponsor value is held while the plan remains in the current season. Because
this milestone does not import a league-calendar boundary, the user may provide weeks to
the boundary. After it, sponsor income is either the explicit post-boundary assumption or
zero with an uncertainty note. If no boundary is provided, current sponsor income is
extrapolated and labeled uncertain.

CHPP financial income/cost remains a current factual observation, but it is deliberately
excluded from future weeks. It may represent balance-dependent interest rather than a
normal fixed recurring amount. Staff, youth, and arena maintenance remain fixed recurring
costs unless the user explicitly overrides them on the plan.

Fixture dates are bucketed relative to the bound finance observation using
`ceil(days / 7)`. Only fixtures within the plan horizon participate. This is a transparent
planning convention, not a claim about Hattrick's exact weekly economic-update timestamp.

## API

- `GET /api/training-plans/{id}/finance` returns bound current facts, arena, fixtures,
  assumptions, and wage-model quality.
- `PUT /api/training-plans/{id}/finance/assumptions` replaces the plan's assumption set.
- `PUT /api/training-plans/{id}/finance/fixtures/{match_id}` stores weather and optional
  club-revenue override for one plan-bound fixture.
- `POST /api/training-plans/{id}/finance/simulate` returns weekly rows, block checkpoints,
  player/squad wages, totals, and uncertainty notes.

## Limits requiring manual validation

- Exact future attendance, sponsor change, and season-boundary timing are unknown. The
  attendance model is an explicitly low-confidence community scenario.
- CHPP `CostsPlayers` may include game-side adjustments not reproduced by summing player
  salary fields. Both are retained as separate facts.
- Wage changes after birthdays use the low-confidence model described in
  `docs/wage-engine.md`.
- Financial income/cost, temporary income/cost, and spectator income are imported but are
  not extrapolated as recurring future flows.
- No financing interest thresholds, bankruptcy behavior, currency localization, or
  capital events are modeled.
