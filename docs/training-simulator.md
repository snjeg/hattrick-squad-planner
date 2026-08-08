# Manual training-cycle simulator

## Scope

Milestone 3 answers one question: **If I follow this manually configured training
plan, what happens to the starting squad?** It does not recommend training types,
switch points, transfers, lineups, tactics, wages, or finances.

The simulator is deterministic and records the Milestone 2 formula reference as
`ho-31622ccd42e104e21a853122ffd269bd9e98dc88`.

## Persistent plan model

- `training_plans` stores the name, exact starting sync, formula version, and timestamps.
- `training_plan_players` captures one immutable factual `PlayerSnapshot` ID per player.
  Its optional JSON overrides hold manually supplied fractional starting skills.
- `training_blocks` stores deterministic order, weeks, training type, coach level,
  assistant total levels, intensity, and stamina share.
- `training_assignments` identifies a starting-plan player and optional set-pieces-taker
  status for one block.
- `training_appearances` stores one or more Hattrick position/minute segments for that
  assignment.

Deleting a plan deletes its hypothetical configuration, never players or factual snapshots.
Plans survive application restarts through normal SQLAlchemy/Alembic persistence.

## Stable starting snapshot

Creating a plan selects the most recent completed sync and captures every player snapshot
from that sync in `training_plan_players`. Later CHPP syncs append factual observations but
do not change an existing plan's inputs. A future “refresh from current squad” operation
must be explicit and should either clone or deliberately rebase a plan.

This approach makes a simulation reproducible and avoids silently rewriting history. It
also makes player entry/exit events a natural future extension: a later event model can add
or remove projected participants without changing the factual starting cohort.

## Starting fractional skills

CHPP supplies visible integer skills. The default estimate is therefore:

```text
fractional starting skill = visible skill + 0.00
```

The API accepts optional manual overrides only within the same visible interval. For
example, visible PM 9 may be overridden with 9.63 but not 10.10. The normal UI keeps the
simple +0.00 assumption visible rather than presenting it as known fact. Automatic
subskill inference remains out of scope.

## Assignments and eligibility

Assignments use Hattrick terms: GK, WB, CD, W, IM, F, minutes, and set-pieces-taker status.
They never accept a raw multiplier. The simulator passes stored appearances to
`resolve_training_exposure()`, which classifies full, partial, osmosis, bonus, or no
training. The UI displays the category and effective fraction returned by the backend.

The API supports multiple appearance segments for mixed positions or two matches. The
Milestone 3 UI deliberately offers one simple position per player; richer match-like
editing can be added without changing persistence or simulation.

## Weekly algorithm

Blocks are sorted by `(sort_order, id)`. For every week in each block:

1. load each player's current projected exact age and fractional skills;
2. resolve the manually planned appearances through the existing eligibility domain;
3. call the Milestone 2 engine once for every skill trained by the training type;
4. store each returned fractional skill as the next week's input;
5. advance age by seven Hattrick days after that week's training;
6. record optional weekly results and continue.

This intentionally does not multiply one weekly gain by the block length. Skill-factor
changes after a visible pop and age-factor changes after a birthday affect later weeks.
Shooting calls the engine separately for Scoring and Set Pieces using the same exposure.

## Two-match capacity model

Capacity is validated separately from the training-speed formula. The model assumes the
normal competitive plus cup/friendly pattern: two 90-minute matches per training week.
It follows the current Hattrick lineup structure and the official 90-minute player
training cap documented in the [Hattrick Rules](https://wiki.hattrick.org/wiki/Rules) and
[line-up documentation](https://wiki.hattrick.org/wiki/3-4-3).

| Position/line | Weekly capacity |
| --- | ---: |
| Goalkeeper | 2 × 90 minutes |
| Wingback | 4 × 90 minutes |
| Central defender | 6 × 90 minutes |
| Winger | 4 × 90 minutes |
| Inner midfielder | 6 × 90 minutes |
| Forward | 6 × 90 minutes |
| All defenders (WB + CD) | 10 × 90 minutes |
| All midfielders (W + IM) | 10 × 90 minutes |
| Whole lineups | 22 × 90 minutes |

Consequences include six full PM IM slots plus four partial winger slots, ten full
Defending slots, six full Scoring slots, four full Winger plus four partial wingback
slots, sixteen full Short Passes positions, and twenty-two Defensive Positions slots.

The validator aggregates minutes by player, position, line, and total lineup. This is a
clear conservative abstraction, not a future-match scheduler. It catches obvious
impossibilities but does not prove that every unusual substitution/mixed-minute allocation
can be arranged into two concrete legal lineups. Automatic lineup generation is out of scope.

## Results and data boundary

Results contain, per player:

- starting exact age and fractional/visible skills;
- exact state and skill-up counts after every block;
- final exact age and fractional/visible skills;
- total gains and skill-ups;
- optional week-by-week gains and states.

`PlayerSnapshot` always means factual CHPP data. Projected state is created in memory and
returned through the simulation API; it is never inserted into `player_snapshots` or
presented as factual. Only plan configuration is persisted.

## Application defaults

CHPP training settings are not imported yet. New blocks therefore use explicit application
defaults: Playmaking, one week, solid (7) coach, ten assistant levels, 100% intensity, and
10% stamina share. These are editable assumptions, not claims about the club's current setup.

## Current limitations and extension points

- Plans simulate only players captured at creation; purchases, sales, and academy promotion
  events are future additions.
- The simple UI edits one position per player, although the API/domain support mixed segments.
- Capacity validation uses aggregate two-match limits and does not generate actual lineups.
- Unknown source skills remain unknown; the engine does not invent a value for them.
- Skill drops, wage changes, finance, market values, match ratings, and tactics are absent.
- Formula changes require a new reference version and explicit reproducibility policy.

