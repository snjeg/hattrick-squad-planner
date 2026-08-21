# Architecture through Milestone 9

## Data flow

```text
Manual sync action
      |
      v
FastAPI sync endpoint
      |
      v
CHPPClient abstraction ----> mock XML fixture
      |                       or OAuth-signed live XML request
      v
XML normalizer
      |
      +----> Player identity (upsert stable factual fields)
      |
      +----> PlayerSnapshot (always append observations)
      +----> FinanceSnapshot / ArenaSnapshot / FixtureSnapshot (append observations)
      |
      v
SQLAlchemy database <---- Alembic-managed schema
      |
      v
Chronologically latest snapshot query ----> React squad table
```

Raw CHPP XML does not cross the adapter/normalizer boundary. The training engine consumes its own explicit normalized values and has no dependency on the CHPP adapter, database, FastAPI, or React.

The selected-lineup engine under `backend/app/team_rating/` is likewise a pure domain. It
consumes Milestone 5 player contributions, applies verified team-layer factors, and returns
seven match-start sector ratings. `team_rating_services.py` materializes current/projected
plan states before entering the domain.

`backend/app/squad_evaluation/` builds deterministic bounded candidate search on the
prepared Milestone 6A boundary. It returns profile-specific lineups plus decomposed peak,
depth, flexibility, rotation, replacement, role-depth, and training-cohort metrics. Planning
roles are request-local and require no schema change. `squad_evaluation_services.py` adapts
supplied states or immutable plan checkpoints and reuses training eligibility for cohort
classification; it never duplicates training or team-rating formulas.

`backend/app/roster_scenario/` composes immutable plan checkpoints with explicit sales,
purchases, and role changes. It calls squad evaluation, consumes plan-projected wage/finance
facts, and returns baseline-relative competitive, training, wage, cash, and coverage evidence.
The domain is policy-free: it does not rank scenarios or emit Keep/Sell/Buy recommendations.
`roster_scenario_services.py` is the SQLAlchemy/FastAPI adapter and never mutates factual rows.

```text
Training-plan checkpoints + finance periods + user transition assumptions
                              |
                              v
                  roster scenario domain
                    /       |        \
                   v        v         v
          squad evaluation  wages   training capacity
                   \        |         /
                    v       v        v
             baseline-relative evidence + low/base/high cash
```

```text
Latest completed sync
      |
      v
TrainingPlan ----> exact TrainingPlanPlayer snapshot references
      |
      +----> ordered TrainingBlocks
                    |
                    +----> positional minute assignments
                              |
                              v
                    capacity validation
                              |
                              v
                    weekly simulator ----> Milestone 2 training engine
                              |
                              v
projected API result ----> React plan/results workspace
```

The same stable plan boundary now feeds finance projection:

```text
TrainingPlan ----> bound FinanceSnapshot + fixtures + explicit assumptions
      |                         |
      v                         v
weekly training states ----> approximate birthday wage projection
                                      |
                                      v
                           weekly operating cash flow
                                      |
                                      v
                         labeled React finance scenario
```

## Persistence and schema evolution

- `players` holds stable Hattrick identity metadata, including specialty, nationality and whether the player receives a mother-club bonus.
- `player_snapshots` holds time-specific age, visible skills, stamina, form, experience, loyalty, injury level, cards, TSI, wage, and foreign status.
- `sync_runs` records each manual import's source and outcome.
- `oauth_credentials` contains the single local user's CHPP access token in live mode.
- `oauth_request_states` temporarily stores OAuth request-token state during authorization.
- `training_plans` and related block/assignment tables persist hypothetical manual configuration.
- `finance_snapshots`, `arena_snapshots`, and `fixture_snapshots` preserve sync-bound CHPP facts.
- `training_plan_finance_assumptions` stores user-owned scenario inputs separately from facts.
- `training_plan_fixture_assumptions` stores optional weather and club-revenue overrides.
- `training_plan_players` references exact factual snapshots; projected weekly states are not tables.

Snapshot rows are append-only. The squad query chooses the newest observation by `observed_at`, then `sync_run_id`, then snapshot `id`, all descending. The latter two fields provide deterministic tie-breaking rather than treating the largest auto-increment ID as chronological truth.

Alembic owns managed schema evolution. The initial revision represents the complete schema through Milestone 1.1 and can adopt the prior unversioned local SQLite schema. FastAPI startup does not silently create production tables; only disposable test setup may use SQLAlchemy metadata creation directly. Schema types and migration operations remain compatible with SQLite and PostgreSQL.

## Training domain

`backend/app/training/` separates reusable concerns:

- `age.py` represents exact Hattrick years and days and deterministic week advancement.
- `types.py` defines skills, positions, training types, and coach levels.
- `factors.py` implements skill, age, coach, assistant, intensity, and stamina factors.
- `coefficients.py` describes each training type and its eligible positions.
- `eligibility.py` resolves full, partial, osmosis, and bonus exposure with the weekly cap.
- `engine.py` composes those values into an immutable fractional-skill result.

The calculation remains a domain service, not route logic. `backend/app/simulator/` adds a second domain boundary for two-match capacity validation and deterministic week-by-week state progression. `plan_services.py` translates persisted records into normalized simulator inputs and serializes outputs; it does not reimplement formulas.

## Manual planning boundary

Plans capture the latest completed sync at creation and retain one exact snapshot reference per starting player. A later sync never silently changes a saved plan. Starting visible skills default to fractional `.00`, with optional same-visible-level manual overrides stored on the plan-player link.

Each block is manual and ordered. Assignments store understandable position/minute segments and are resolved by the existing eligibility module. Capacity rules are independent of training speed. Simulation results are hypothetical in-memory data and are never written to `player_snapshots`.

## Wage and finance domains

`backend/app/wage/` projects factual player salary unchanged until a simulated birthday,
then applies the explicitly low-confidence approximation documented in
`docs/wage-engine.md`. The module depends on normalized age/skill states, not CHPP,
FastAPI, or React.

`backend/app/finance/` consumes fixed staff/youth/arena costs, projected weekly squad
wages, fixture events, and explicit assumptions. It keeps operating and capital cash flow
separate and does not infer transfer proceeds or recommendations. `backend/app/attendance/`
provides a standalone seat-level community estimate with explicit weather uncertainty;
the finance service selects it only when the required facts and assumed weather exist. Imported
financial income/cost remains factual but is not extrapolated because it can depend on the
club's changing balance.
`finance_services.py` translates between plan-bound database facts and these independent
domains.

## Product surface reset

Contribution, team-rating, squad-evaluation, roster-scenario and rolling-optimizer domains
remain internal capabilities. Milestone 9 removes their standalone frontend workspaces
rather than deleting verified calculation code.

The React product now exposes four areas only: Squad, Strategy, Training Plan and Finance.
Strategy controls preferred formations and primary tactic, then renders normal orders
compactly with optional individual-order inspection. Training Plan is a manual “what
happens if?” sandbox; Finance is a separate primary workspace.

## Rolling optimizer domain

`backend/app/optimizer/` is a framework-independent receding-horizon layer over the
existing training simulator, wage projection, roster-scenario, and whole-squad domains.
It generates bounded training/duration/cohort candidates, caches identical simulations,
prunes only conservatively comparable dominated paths, and compiles finalists into
`RosterScenarioRequest` checkpoints for full evaluation. Centralized objective profiles
change weights, not code paths.

`optimizer_services.py` is the only database adapter. It binds a recommendation to the
plan's immutable factual snapshot and finance assumptions. The optimizer never writes
player history, projected states, or recommendations to factual tables. Its serializable
result carries input/model versions so lightweight run persistence can be added later
without persisting intermediate search trees. See `docs/rolling-optimizer.md`.

The Milestone 8 optimizer is retained but is not the new Strategy user experience. A later
optimizer must reason from tactical identity through position/skill requirements, gaps,
whole-cohort training geometry and deterministic candidate cycles before producing a
roadmap.

## Strategy matrix domain

backend/app/strategy is a framework-independent boundary for football identity and the
Position × Skill × Tactical Context Matrix. It imports the existing immutable contribution
coefficient map rather than copying it. Direct coefficient totals and within-row dot
normalization are constructed independently from tactic overlays.

strategy_services.py adapts typed preferences to the domain and serializes the result.
POST /api/strategy/matrix validates formations against the existing legal-formation set,
returns all 19 role/order profiles and never reads or writes factual player rows.

Strategy preferences are request-scoped in Milestone 9. This intentionally avoids a
single-global-row persistence model before team/user ownership exists.

## Player contribution domain

`backend/app/contribution/` is a framework-independent individual-player primitive. It
combines fractional skills, factual form/stamina/experience/loyalty/homegrown/specialty,
one legal position/order/side, and explicit weather into seven raw sector contributions.
Its coefficient map and modifiers are pinned to the audited current HO Schum model in
`docs/player-contribution-engine.md`.

`contribution_services.py` reads a plan's immutable factual snapshot, combines it with
simulator-projected trainable skills at each block checkpoint, and serializes a
current-versus-projected comparison. It never persists projected state.

The contribution vector is deliberately pre-team. It excludes overcrowding, team spirit,
home advantage, attitude, coach/team modifiers, tactics, nonlinear displayed-sector
conversion, lineup enumeration, and recommendations. Relevant HO team-layer research is
documented for Milestone 6 but is not implemented here.

## CHPP boundaries and credential safety

The integration uses only CHPP OAuth and XML endpoints. It does not accept Hattrick passwords, scrape HTML, schedule downloads, submit match orders, or automate transfers. Mock mode remains the default and follows the same parser and persistence path as live data.

Plaintext OAuth-token storage exists only to support single-user local development. It is forbidden for hosted or multi-user deployment; hosted work requires a separate encrypted credential-store design.

## Current limits

- Live CHPP behavior requires approved application credentials and manual validation.
- The squad-list response reports the mother-club bonus but not the mother club's team identity; HO obtains that identity from a separate player-details response.
- Specialty remains a numeric CHPP value until its labels are verified from an authoritative source.
- Fractional starting skills default to visible +0.00; automatic inference remains future work.
- The simple plan UI supports one appearance per player while the API supports mixed segments.
- Capacity is an aggregate two-match validator, not an automatic lineup or match simulator.
- Exact wages or attendance, stadium optimization, market search, match-result prediction,
  and autonomous recommendation execution remain out of scope. Milestone 8 emits bounded,
  evidence-backed training and roster preparations but does not search actual market
  players. Wage and attendance results remain labeled approximations, not verified
  reproductions of Hattrick's private formulas.
- The Strategy matrix describes sourced requirements but does not yet derive target skill
  levels, skill gaps, candidate cycles or a ranked roadmap.
- Strategy preferences are typed request/UI state rather than persisted user/team settings.
