# Roster transition scenario engine

## Scope and decision boundary

Milestone 7 evaluates explicit roster changes at training-plan checkpoints. It answers
"what happens if this transition occurs?" It does not decide what to train, when to switch,
which player to buy, or whether a player should be sold.

The engine deliberately supports statements such as:

> This sale has a small modeled competitive cost, removes the player's weekly wage,
> opens one aggregate training place, and adds the user-assumed transfer proceeds.

It does **not** append "therefore sell him." Keep/Sell/Buy labels appear only when the user
created that action. Milestone 8 owns decision policy and search across scenarios.

The pure domain lives in `backend/app/roster_scenario/`. It imports other domain engines but
does not import SQLAlchemy, FastAPI, CHPP, or React. The plan adapter materializes immutable
training-plan projections, finance periods, and factual player metadata before calling it.
No projected state is written to `PlayerSnapshot`.

## Scenario model

A request contains ordered base checkpoint states, an opening cash balance, match context,
evaluation profiles/search bounds, and one or more named scenarios. A scenario contains:

- stable scenario and transition IDs;
- zero or more sell, buy, and planning-role transitions;
- scenario-local hypothetical players with IDs such as `hyp:future-im-1`;
- manual low/base/high transfer assumptions;
- optional cash/spend constraints;
- optional retention-intent metadata.

The engine always synthesizes a no-transition baseline named "Keep current squad through the
plan." It returns every dimension separately and does not rank scenarios.

## Checkpoints and transition order

Plan checkpoints are `current`, `after_block:{block_id}`, and `final`. When several changes
share a checkpoint, the stable order is:

1. finish the preceding training block and load its projected player state;
2. execute sales, ordered by transition ID;
3. execute purchases, ordered by transition ID;
4. apply planning-role changes, ordered by transition ID;
5. run squad evaluation and training-cohort/coverage analysis;
6. carry the resulting wage bill into the following period.

Transfer cash is immediate at the checkpoint. The application does not invent intra-week
timing. A current transition is applied before the first block. An `after_block` transition
cannot alter earlier checkpoints.

At a checkpoint, training participation describes the **next** block. Thus a purchase after
Playmaking and before Passing can fill a Passing place without being treated as present during
Playmaking. `final` has no following training capacity.

## Sell semantics

A sale removes the player from all later roster states, wages, squad evaluations, and training
cohorts. Proceeds use only the user's low/base/high assumption, less any explicit transfer cost.
Selling an absent player or selling the same player again is rejected.

Player-level evidence includes competitive-score change, the existing Milestone 6B replacement
drop where the player was in the primary XI, contextual role-depth change where identifiable,
training-capacity change, wage relief, and transfer cash. It also returns the replacement
formation and the selected-lineup contribution surface calculated through Milestone 5 when the
player participates. These values are evidence, not a Sell recommendation.

## Buy and hypothetical-player semantics

Hypothetical players are assumptions, not CHPP facts. A complete profile requires exact age,
all seven skills, stamina, form, experience, loyalty, foreign status, planning role, and optional
position constraints. Mother-club bonus is always false for an acquisition. Missing attributes
are rejected instead of filled with averages.

The plan adapter simulates a hypothetical only from its acquisition checkpoint through later
manual blocks, using only explicit block assignments. It reuses the training engine and
eligibility resolver. Buying the same hypothetical twice is rejected. The response labels every
roster entry as factual or hypothetical.

User-defined acquisition templates are request-local profiles; v1 does not persist or globally
hard-code profiles such as "future core IM."

## Wages

Existing players use the plan's current factual wage and existing birthday projection.
Hypothetical players can use:

- a supplied wage assumption; or
- the existing low-confidence community wage estimate from their complete skill profile.

The current foreign-player surcharge and specialty handling are reused. Responses expose
`wage_source` as factual, supplied assumption, or model estimate. Buying earlier carries wages
for more weeks; the engine reports that cost without choosing an acquisition time.

## Finance and transfer ranges

Operating cash flow remains separate from capital/transfer cash flow. The plan adapter reuses
the Milestone 4 weekly operating projection as the baseline, then adjusts subsequent periods for
the scenario wage delta.

- sale: positive transfer cash flow;
- purchase: negative transfer cash flow;
- staff, youth, and arena maintenance remain fixed recurring costs from the finance model;
- balance-dependent financial income/cost is not extrapolated;
- low/base/high cash paths use only manual transfer values.

Each checkpoint exposes opening cash, operating flow, transfer flow, closing cash, cumulative
transfer balance, and cumulative spend. Minimum-reserve and spend constraints create explicit
violations; they do not silently discard a scenario.

## Squad, training, deltas, and coverage

Every evaluable checkpoint calls Milestone 6B using the scenario's active roster, same match
context, profiles, legal formations, and bounded search configuration. Local deterministic
memoization reuses identical roster evaluations across the baseline and scenarios.

Outputs include composite score and its peak/depth/flexibility/rotation components, wages, cash,
roster size, role distribution, training participation, and unused aggregate capacity. Deltas
are computed against the no-transition baseline at the same checkpoint.

Meaningful training capacity uses the existing two-match positional caps for full and partial
training positions. It remains an aggregate model, not an automatic appearance scheduler.
Coverage gaps are descriptive (`legal_xi`, goalkeeper, inner midfield, winger) and never become
automatic purchase instructions. Fewer than eleven non-EXIT players produces warnings and no
squad evaluation instead of a fabricated rating.

## API and UI

`POST /api/roster-scenarios/evaluate` accepts already-materialized checkpoint states for
external/domain callers. `POST /api/training-plans/{plan_id}/roster-scenarios/evaluate`
materializes the same request from a saved plan. Both accept multiple named scenarios.
The Roster Scenarios workspace currently provides a compact single-action editor for a sale or
hypothetical acquisition, checkpoint/price controls, a hypothetical-player editor, baseline
comparison, checkpoint timeline, low/base/high finance, and transition evidence. The API/domain
already support paired and multi-transition scenarios and role changes.

## Limitations and Milestone 8 bridge

- Transfer prices and optional resale values are not inferred. There is no scraping or market
  search.
- V1 scenario definitions are serialized request data but are not persisted as database rows.
- The UI exposes one action at a time; API callers can submit multiple transitions.
- Existing manual training assignments are not automatically rescheduled after a sale. A sold
  player's place becomes unused; the engine does not invent a replacement appearance.
- Contribution and team formulas retain their documented community uncertainty.
- Squad evaluation is bounded "best found," not a global optimum.
- There is no scenario objective, automatic ranking, or recommendation history yet.

Milestone 8 can construct these same versioned scenario primitives while searching training
sequence, block length, and transition timing. It should consume this engine rather than
duplicate roster, finance, wage, or training-transition behavior.
