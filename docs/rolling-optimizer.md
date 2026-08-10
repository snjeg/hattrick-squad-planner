# Rolling training and squad optimizer

## Purpose and boundary

Milestone 8 answers: “what is the best-supported next move?” It is a deterministic,
receding-horizon decision aid. It recommends one next block, exposes a plausible
multi-block path, and expects to be rerun after a sync, transfer, pop, injury, finance
change, or manual value update. It does not claim a globally optimal permanent plan and
does not execute transfers or scrape the market.

The domain lives in `backend/app/optimizer/` and has no FastAPI, SQLAlchemy, or CHPP
dependency. `optimizer_services.py` adapts an immutable saved plan to normalized domain
inputs. Candidate checkpoints are compiled into Milestone 7 `RosterScenarioRequest`
baseline states and evaluated by the existing whole-squad scenario engine. Wages use the
existing wage projector; training uses the Milestone 2 engine and simulator.

## Objective

All modes use the same nine normalized dimensions:

| Dimension | Team first | Balanced | Profit first |
| --- | ---: | ---: | ---: |
| Peak strength | .28 | .18 | .10 |
| Depth | .16 | .12 | .08 |
| Formation flexibility | .10 | .08 | .05 |
| Rotation | .08 | .07 | .05 |
| Training efficiency | .13 | .15 | .18 |
| Transfer value | .04 | .13 | .25 |
| Wage efficiency | .08 | .10 | .11 |
| Capital efficiency | .05 | .08 | .10 |
| Liquidity | .08 | .09 | .08 |

These are product presets, not Hattrick facts. They are centralized in
`optimizer/weights.py`, versioned as `rolling-objective-v1`, and may be replaced with
finite, non-negative custom weights. Custom weights are normalized transparently.

Competitive checkpoint values are discounted by `0.985 ** optimizer_week`. The default
is a modest planning preference rather than an empirical Hattrick constant. Training
efficiency is `1 - unused meaningful slot-weeks / available meaningful slot-weeks`.
Full/partial position capacity uses the existing eligibility and capacity layer; osmosis
and Set Pieces bonus exposure remain beneficiaries but do not consume an ordinary scarce
slot.

Transfer value is included only when the manager supplies low/base/high assumptions.
Missing values lower confidence. No hidden valuation or season-price formula is used.

## Candidate blocks and cohorts

Every one of the eleven Milestone 2 training types is considered. For each type the
assignment planner ranks all non-Exit players across its full and partial positions, then
uses the existing weekly position caps. It records full, partial, mixed, osmosis, and
bonus exposure separately. The cheap ranking signal combines:

- exact HO-based fractional gain;
- a documented search-pruning skill relevance weight;
- the player's planning role;
- allowed/preferred positional fit.

This signal only prunes candidates. Final plan value comes from whole-squad scenario,
finance, wage, and capacity evaluation. It is not a replacement for the player
contribution or squad engines.

Default duration seeds are 3, 5, 7, 9, 12, and 16 weeks. The simulator adds nearby
visible-pop events, scores the bounded set, and retains the strongest durations for each
type. A switch window is the earliest/recommended/latest duration within six percent of
the winning type's pop-informed marginal proxy. It is deliberately a window, not a fake
exact date. Existing training receives a small configurable continuity/friction signal;
switch-now candidates remain available.

## Search

The default horizon is 48 weeks (configurable 16–256), depth three, beam width twelve,
six next-training types, four durations per type, and five full scenario evaluations.
The search:

1. generates and caches one-block simulations for all types;
2. retains the strongest types and duration events;
3. expands different following blocks up to the configured depth/horizon;
4. conservatively prunes plans only when equal-horizon/same-ending-training candidates
   are no better in both proxy value and capacity utilization;
5. fully evaluates the bounded finalists through the roster-scenario and whole-squad
   engines.

Diagnostics report candidates, pruning, cache hits, full evaluations, beam width, and
depth. `global_optimality_claimed` is always false and alternatives say “best found.”

## Roster timing evidence

Keep decisions are temporal: retain relevant Core, Rotation, or Development players
through the recommended block and then re-evaluate. Sale candidates combine planning
role, top-lineup frequency, bounded replacement drop, wage relief, training-capacity
release, and manager-supplied transfer assumptions. A candidate is evidence, not an
autonomous transfer action.

Bounded sale timing events are:

- now;
- after the next projected visible pop;
- at the current useful block end;
- before the exact Hattrick birthday;
- at the start of a stronger community market window;
- before a later-block replacement/acquisition liquidity need.

Training switches and sale dates are independent. Exact age uses 112-day Hattrick years.
No universal birthday discount is assumed.

When later blocks have unused meaningful capacity, the optimizer emits clearly
hypothetical acquisition profiles: role, age range, trained-skill ranges, planning role,
latest useful week, and optional manager-supplied low/base/high price and wage. A profile
is delayed until shortly before its useful block so it does not silently incur early
wages or capital use. It is not a fabricated market player.

## Season calendar and market uncertainty

`community-seasonality-v1` is qualitative:

| Hattrick season week | Classification |
| --- | --- |
| 1–4 | Very strong |
| 5–7 | Strong |
| 8–10 | Normal / softer |
| 11–14 | Very weak |
| 15–16 | Strong / strengthening |

The calendar rolls across 16-week season boundaries and preserves the season number when
provided. It exposes weeks until a stronger window. These community observations do not
modify money values. Unknown season week lowers confidence. Hour, weekday, auction
deadline, and listing-price optimization are out of scope.

## Sensitivity, confidence, and constraints

Low/base/high supplied transfer cases are rescored. If the leading next training changes,
confidence falls. Confidence also falls when player values or the calendar are missing.
Formula and wage uncertainty remain documented rather than converted into a fake numeric
confidence percentage.

Hard constraints support minimum cash, maximum capital use, wage ceiling, minimum roster
size, goalkeeper/IM coverage, squad score, and depth. Because v1 emits abstract
acquisition/sale preparations rather than selecting a priced transition into the winning
path, `max_transfer_spend` becomes operative only when a concrete transition is supplied
to the roster-scenario layer.

## API and UI

`POST /api/training-plans/{plan_id}/optimize` accepts objective mode/custom
weights, current training, search bounds, team context, finance/squad constraints,
calendar, transfer assumptions, and abstract acquisition assumptions. The Strategy
workspace displays recommended-now, switch window, timeline badges, cohort, objective
evidence, sale timing, acquisition preparations, alternatives, uncertainty, and search
diagnostics.

## Known limitations

- Future transitions are currently recommendations/evidence derived from the evaluated
  baseline path; v1 does not jointly select a buy/sell pair inside every beam node.
- Static user projected-value assumptions are not an automatic skill-to-price curve.
- Historical optimizer-run persistence and comparison is deferred; the response is
  serializable and includes the factual state/model versions needed for later storage.
- The assignment stage is deterministic and greedy before whole-squad evaluation; it is
  bounded, not an exhaustive weekly lineup/training assignment search.
- Market seasonality remains qualitative until defensible empirical data or explicit
  manager multipliers are available.
