# Selected-lineup team rating engine

## Scope and reference

Milestone 6A evaluates one explicitly supplied senior XI at match start. It does not search
the squad, choose a formation, recommend an XI, predict chances, or simulate a result.

The implementation was audited on 2026-08-09 against Hattrick Organizer commit
`b58f36e2eecc98ba14d88be49c3042c575698134`. The primary source is
`core/rating/RatingPredictionModel.java`; `RatingPredictionManager.java` confirms active
model construction. Display labels follow `core/constants/player/PlayerAbility.kt`.
These are community Schum/HO estimates, not official Hattrick disclosures.

## Exact operation order

HO `calcSectorRating` materializes the players, calculates role-group overcrowding, obtains
each Milestone 5 positional contribution, applies overcrowding to the positional part, adds
experience, applies individual weather and match-minute stamina, sums all players, applies
team/lineup factors, and finally performs nonlinear sector conversion. Milestone 6A evaluates
minute zero, where HO stamina is exactly 1.0. It reuses the Milestone 5 engine and its exposed
pre-experience decomposition; it does not copy the individual contribution tables.

## Lineup and overcrowding

The engine requires eleven distinct player IDs, exactly one goalkeeper, and one of HO's ten
structural senior formations: 3-4-3, 3-5-2, 4-3-3, 4-5-1, 5-3-2, 5-4-1, 4-4-2, 5-2-3,
5-5-0, or 2-5-3. Slot limits are two wingbacks, three central defenders, two wingers, three
inner midfielders, and three forwards.

| Group | Two players | Three players |
| --- | ---: | ---: |
| Central defender | 0.964 | 0.900 |
| Inner midfielder | 0.935 | 0.825 |
| Forward | 0.945 | 0.865 |

The factor applies before experience. Wingbacks, wingers, and the goalkeeper remain 1.0.

## Team factors

Midfield receives `0.1 + 0.425 * sqrt(team spirit)`. HO team spirit is a visible integer
0-10 plus a quarter sublevel 0-3, so the domain accepts 0 through 10.75. Play it Cool is
0.83945, Match of the Season 1.1149, home 1.19892, and away derby 1.11493.

Coach style is HO's match style from -10 (fully defensive) through +10 (fully offensive),
not training coach level or leadership. At balanced/0, defense and attack receive 1.02.
Endpoints are defense 1.15/0.90 and attack 0.90/1.10. Confidence is integer 0-9 and attacks
receive `0.8 + 0.05 * (confidence + 0.5)`.

Verified ordinary-sector tactic modifiers are separate from tactic strength:

- Counter-attacks: midfield 0.93.
- Long shots: midfield and attacks 0.96.
- Attack in the middle: side defenses 0.85.
- Attack in wings: central defense 0.85.
- Play creatively: defenses 0.93.
- Pressing and normal: no match-start sector multiplier in this call path.

Tactic strength, chance redistribution, events, and result prediction are excluded.

## Conversion and display

For positive adjusted contribution `x`, HO returns
`(x * sector_scale) ** 1.2 / 4 + 1`; non-positive input returns 0.75.

| Sector | Scale |
| --- | ---: |
| Midfield | 0.312 |
| Side defense | 0.834 |
| Central defense | 0.501 |
| Side attack | 0.615 |
| Central attack | 0.513 |

The response preserves raw sum, team factor, adjusted sum, continuous displayed number,
level label, and quarter label (very low, low, high, very high). The continuous number is
the calculation boundary; labels are presentation.

## API and plan adapter

`POST /api/team-ratings/calculate` evaluates supplied normalized player states.
`POST /api/training-plans/{plan_id}/team-ratings` evaluates the same manually selected IDs
at `current`, `after_block` (with `block_id`), or `final`. Simulation remains in memory and
the adapter never mutates factual snapshots.

## Deferred and uncertain mechanics

- HO match-average team ratings recalculate the full team through time, applying stamina
  before aggregation and nonlinear conversion. A scalar average is not equivalent, so 6A
  exposes match-start only.
- Formation experience is stored/displayed by HO, but the pinned `calcSectorRating` path
  does not consume it. Confusion appears as match-event state rather than a verified
  deterministic sector multiplier. Neither is invented.
- Man marking, substitutions, cards, special events, and result simulation are deferred.
- Compare the same XI manually in HO before using this as a Milestone 6B high-volume search
  primitive; community formulas may change.
