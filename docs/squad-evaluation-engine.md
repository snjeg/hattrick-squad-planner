# Squad evaluation engine

## Why squad quality is not best-XI quality

Milestone 6B evaluates a current or simulator-projected senior squad across useful legal
lineups. Peak lineup strength is only one output and only 40% of the optional composite.
A squad can therefore score better with slightly lower peak strength when it has stronger
one-player replacements, rotation options, and competitive formations. The decomposed
metrics remain the primary API; the composite is a convenience, not an official Hattrick
rating or a transfer recommendation.

The pure domain lives in `backend/app/squad_evaluation/`. It accepts normalized
`PlayerMatchState` values and calls the Milestone 5 contribution and Milestone 6A prepared-
lineup paths. It does not call CHPP, SQLAlchemy, FastAPI, React, the wage engine, or finance.

## Planning roles

Planning roles are request/checkpoint-local labels and never mutate factual snapshots:

- `CORE`: expected major competitive player over the planning horizon.
- `ROTATION`: regularly useful in alternate formations or contexts.
- `DEVELOPMENT`: primarily building toward future competitive importance.
- `PROFIT_TRAINEE`: primarily occupies training capacity for a later sale.
- `SPECIALIST`: narrow position/order/formation alternative.
- `BACKUP`: low-frequency injury, suspension, or positional cover.
- `EXIT`: present now but excluded from intended-squad evaluation unless explicitly included.

Except for optional `EXIT` exclusion, labels do not alter football calculations. A profit
trainee receives competitive credit when actually selected by useful lineups; a core label
cannot make a weak player rate better. Development value emerges when projected checkpoint
skills improve. Market value and Keep/Sell/Buy language are deliberately absent.

## Candidate generation and formations

The evaluator supports all ten Milestone 6A formations: 2-5-3, 3-4-3, 3-5-2, 4-3-3,
4-4-2, 4-5-1, 5-2-3, 5-3-2, 5-4-1, and 5-5-0. It does not privilege 3-5-2.

For every physical position slot it calculates legal player/order alternatives with the
pinned Milestone 5 engine. It keeps up to two order alternatives for each shortlisted
player, so a player is not reduced permanently to one “best position.” Manually supplied
allowed positions are hard constraints; preferred positions only provide a tiny deterministic
beam-ordering tie break and never change final utility.

Search is a deterministic bounded beam:

1. Generate structural slot templates for each legal formation.
2. Remove exact left/right mirror templates because all v1 profile weights are symmetric.
3. Shortlist a bounded number of distinct players per slot while retaining order alternatives.
4. Expand partial XIs without duplicate players.
5. Keep a versioned beam and evaluate complete candidates through Milestone 6A.
6. Deduplicate exact assignments and retain diverse lineups.

The default has 91 structural templates, beam width 40, 14 distinct candidates per slot,
10 complete evaluations per template, and 10 retained lineups per profile. All limits are
validated and returned in diagnostics. Diversity accepts a different formation, at least
two player changes, or a material normalized sector-profile difference. Responses say
“best found”; the search does not claim exhaustive global optimality.

## Evaluation profiles and utility

Milestone 6A's seven continuous displayed sector values use a common HO rating scale but
are already nonlinear. Milestone 6B therefore compresses each sector before weighting:

```text
normalized_sector = min(1, log1p(max(0, displayed - 0.75)) / log1p(20 - 0.75))
lineup_utility     = sum(normalized_sector * profile_weight)
```

This maps Divine/20 to 1.0 and prevents a single extreme displayed sector from dominating.
It is an application comparison model, not an official match-outcome model.

| Profile | Midfield | Defense total | Attack total |
| --- | ---: | ---: | ---: |
| Balanced | 0.30 | 0.35 | 0.35 |
| Possession | 0.50 | 0.25 | 0.25 |
| Defensive | 0.25 | 0.55 | 0.20 |
| Attacking | 0.25 | 0.20 | 0.55 |

Each defense or attack total is divided equally across its three sectors. Profiles change
only these centralized weights; they share contribution, lineup, context, and search code.

## Depth, replacement sensitivity, and rotation

Replacement sensitivity is evaluated for each player in the primary profile's top found XI:

```text
replacement_drop = peak utility - best evaluated utility without that player
```

Only one unavailable player is modeled. The replacement comes from the evaluated candidate
pool, not an injury probability or multiple-absence simulation. Positional depth ranks a
player by the best retained whole-lineup utility in which he actually occupied goalkeeper,
wingback, central defense, inner midfield, winger, or forward. It is not an isolated player
rating.

Rotation quality reports peak utility, the mean utility of retained distinct lineups, and
the mean best one-starter-excluded utility. Top-K participation and useful position/order
pairs are descriptive redundancy signals, not player-value or sale signals.

Formation flexibility reports the top found lineup for every legal formation and its
utility gap from the primary-profile best. It does not simulate opponents, chances, or
results.

## Composite squad score

The optional 0-100 composite is versioned and decomposable:

| Component | Weight | Construction |
| --- | ---: | --- |
| Peak strength | 0.40 | primary-profile top utility |
| Depth resilience | 0.25 | mean one-starter replacement ratio |
| Formation flexibility | 0.20 | mean formation-best ratio |
| Rotation quality | 0.15 | mean of distinct-lineup and starter-exclusion ratios |

Peak/balanced/formation results are not summed separately, avoiding obvious duplicate
counting of the same XI. Transfer value, wages, cash, training efficiency, and hypothetical
acquisitions are excluded.

## Training cohort and checkpoints

The plan adapter reuses simulator states and training eligibility. It classifies each member
as full, partial, osmosis, bonus, mixed, or none and reports planning-role/training overlap.
For `current`, the cohort describes the first block; `after_block`, the named block; and
`final`, the last block. With no blocks every member is untrained. This is descriptive and
does not penalize non-starters or recommend a different training plan.

Plan evaluation supports current, after one block, final, or all checkpoints. Only skills
projected by the existing simulator change. Form, stamina, experience, loyalty, mother-club
status, and specialty stay at the plan's frozen factual snapshot, matching existing plan
projection conventions. No projected state is persisted as fact.

## API and frontend

- `POST /api/squad-evaluations/calculate` evaluates supplied normalized members.
- `POST /api/training-plans/{plan_id}/squad-evaluation` evaluates plan-local roles at one or
  all checkpoints.

The Squad Evaluation UI assigns planning roles, chooses one explicit profile, compares
checkpoint components, shows formation flexibility and replacement sensitivity, summarizes
the training cohort, and opens a generated lineup for player/order and seven-sector
inspection. It displays bounded-search diagnostics and uncertainty language.

## Known limitations and later milestones

- Search is bounded and deterministic, not a guaranteed global optimum.
- Left/right mirror pruning is valid only while profile weights and context remain symmetric.
- Replacement sensitivity uses one-player absence and the evaluated pool.
- Match-average stamina, formation confusion, injuries, suspensions, opponent-specific
  planning, chance distribution, tactic strength, and result simulation remain excluded.
- Role labels are one-checkpoint inputs; role-transition scheduling is future work.
- Milestone 7 may consume decomposed metrics to compare removals/acquisitions, but 6B makes
  no Keep/Sell/Buy recommendation.
- Milestone 8 may combine competitive value with training efficiency, wages, capital,
  transfers, and rolling planning. None of those weights belong in this competitive domain.
