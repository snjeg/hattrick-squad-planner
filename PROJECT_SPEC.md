# Hattrick Training Strategy Planner

## Product purpose

This application helps a Hattrick manager design efficient, financially feasible senior-team
training cycles. Its core question is:

> Given my current squad, the players I want to build, the way I want the team to play,
> training-slot geometry, future acquisitions and finances, what training path should I
> follow?

This specification supersedes the former general squad-management-suite direction. Verified
calculation engines built under earlier milestones remain useful internal capabilities, but
they are not separate products the manager must operate.

## Primary product areas

The user-facing product has exactly four primary areas:

1. **Squad** — the factual CHPP-derived baseline and its append-only observation history.
2. **Strategy** — football identity, position/skill requirements and eventually the proposed
   training roadmap. This is the core product.
3. **Training Plan** — a manual sandbox answering “If I train this cohort this way, what
   happens?”
4. **Finance** — a labeled cash forecast and, later, a Strategy feasibility constraint.

Individual Contribution, Lineup Evaluation, Squad Evaluation and Roster Scenarios are not
primary workspaces. Their verified backend engines may be consumed internally by Strategy.

## Non-negotiable factual boundary

Player and PlayerSnapshot represent factual imported state. A successful sync appends a new
snapshot observation and may update genuinely stable player identity metadata.

Training plans, strategy preferences, manual overrides, future-player placeholders,
simulations, finance assumptions and optimizer results are hypothetical. They must never:

- mutate a factual player snapshot;
- replace the latest factual squad with projected state;
- delete player identity or snapshot history when a plan is deleted;
- silently turn estimated fractional skills into imported facts.

Plans reference the exact factual snapshots from their starting sync. Projected states remain
in domain/API output.

## Strategy architecture

The future Strategy Optimizer should follow this evidence chain:

~~~text
TACTICAL IDENTITY
        ↓
POSITION × SKILL REQUIREMENTS
        ↓
CURRENT + FUTURE PLAYERS
        ↓
SKILL GAPS
        ↓
TRAINING SLOT GEOMETRY
        ↓
CANDIDATE TRAINING CYCLES
        ↓
DETERMINISTIC SIMULATION
        ↓
RANKED ROADMAP
        ↓
NEXT TRAINING BLOCK
~~~

The optimizer must derive feasible cycles from actual requirements. Sequences such as
Playmaking → Passing → Winger or Defending → Playmaking → Passing are examples, never
universal defaults. The next optimizer should compare complete candidate cycles
deterministically before recommending the immediate block.

### Position × Skill × Tactical Context Matrix

The source-backed Strategy foundation contains seven skill columns:

- Goalkeeping
- Defending
- Playmaking
- Winger
- Passing
- Scoring
- Set Pieces

Rows cover Goalkeeper, Wingback, Central Defender, Winger, Inner Midfielder and Forward.
Every legal individual order supported by the audited contribution engine remains distinct.
Normal order is the compact default; other orders are inspectable.

Each cell keeps two independent layers:

- **Direct positional contribution** comes exclusively from the existing pinned Hattrick
  Organizer sector coefficients.
- **Tactical relevance** comes from a separate source-audited overlay and may be
  quantitative only when a reliable relative relationship is documented.

The tactical layer cannot change direct coefficients. A zero direct value remains zero even
when a tactic makes that skill strategically important.

Supported identities are Normal, Attack in the Middle, Attack on Wings, Counter Attacks,
Pressing, Play Creatively and Long Shots. Unsupported precision is represented as
qualitative evidence, not invented weights.

### Formation preferences

The manager may select one or more formations from the legal formation set already enforced
by the team-rating domain. No formation is a universal default. In Milestone 9 these
preferences are explicit request/UI state; the domain validates and echoes them so a later
optimizer contract can consume them without a premature persistence migration.

## Whole-cohort training geometry

Strategy must reason about the complete weekly cohort rather than only a best XI. Existing
eligibility and capacity semantics remain authoritative: full, partial, osmosis and bonus
exposure are distinct; only compatible meaningful full/partial exposure consumes scarce
capacity.

For example, Short Passes may involve six inner midfielders, four wingers and six forwards
across the weekly match schedule. Actual capacity is derived from the training definition
and assignments, not a fixed best-XI assumption.

## Current and future players

Future candidate cycles may contain:

- suitable current factual players, projected without mutating their snapshots; and
- explicit future-acquisition placeholders.

A future placeholder should eventually carry intended archetype/position, age range,
relevant skill ranges, optional specialty preference, first useful block and role in the
cycle. Acquisition needs must be derived:

~~~text
required cohort − suitable current players = missing future cohort
~~~

The timing principle is to acquire a future core player shortly before the first block that
materially benefits him, not automatically at the beginning of the entire roadmap. Milestone
9 documents this contract but does not search the market or build the cycle optimizer.

## Training Plan

Training Plan is a deterministic manual sandbox. It supports ordered blocks, source-backed
positional exposure, fractional skill simulation, age progression and plan-bound finance.
It does not require the manager to already know the optimal multi-season cycle.

Future Training Plan work may allow placeholders proposed by Strategy alongside current
players. Every hypothetical state must remain clearly labeled and isolated from factual
history.

## Finance

Finance is both a standalone forecast and a future Strategy constraint. It should combine,
when available:

- factual cash, sponsors, wages and recurring costs;
- factual future home/away league, cup and relevant friendly fixtures;
- arena, supporter/fan and weather scenario inputs;
- labeled attendance and post-birthday wage estimates;
- explicit planned transfer assumptions.

Known, assumed, community-estimated and projected values remain distinguishable. No market
scraping, invented transfer price or automatic transaction is allowed.

## Internal calculation capabilities

The following framework-independent domains remain available for internal composition:

- training and weekly simulation;
- individual contribution;
- selected-lineup team ratings;
- bounded squad evaluation;
- roster scenarios;
- wage, attendance and finance projection;
- the Milestone 8 bounded rolling optimizer.

The Milestone 8 optimizer is retained but is no longer exposed as the Strategy product. It
must not be cosmetically renamed or treated as the completed deterministic cycle optimizer.

## CHPP and local-data constraints

- Use approved CHPP OAuth/XML endpoints only.
- Never request or store a Hattrick password.
- Sync is manual and user initiated.
- No HTML scraping, automated match orders, market bidding or transfer execution.
- Plaintext local OAuth token storage is development-only and forbidden for hosted
  multi-user deployment.
- Alembic owns managed schema evolution; migrations remain SQLite and PostgreSQL compatible.

## Milestone 9 deliverables

- simplify primary navigation to Squad, Strategy, Training Plan and Finance;
- remove old analytical workspace presentation while retaining useful backend engines;
- add the framework-independent Strategy matrix domain and API;
- source-audit tactic overlays and label uncertainty;
- add the dense two-layer Strategy matrix UI and formation/tactic controls;
- prove the entire training-plan lifecycle preserves factual squad identities and snapshots;
- update product, architecture and decision documentation.

Milestone 9 does **not** rewrite the optimizer, rank full cycles, discover transfers, predict
matches or optimize opponents/stadiums.

## Milestone 10 decision boundary

Before implementing the deterministic cycle optimizer, decide:

- how strategy preferences are owned/persisted once team/user identity is explicit;
- the objective profile and roadmap comparison contract;
- the placeholder acquisition schema and when placeholders become plan members;
- how target skill requirements are derived without invented universal target levels;
- which tactic effects remain qualitative during ranking;
- how optimizer runs and model versions are retained for reproducibility.
