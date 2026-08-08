# Architecture through Milestone 3

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
      |
      v
SQLAlchemy database <---- Alembic-managed schema
      |
      v
Chronologically latest snapshot query ----> React squad table
```

Raw CHPP XML does not cross the adapter/normalizer boundary. The training engine consumes its own explicit normalized values and has no dependency on the CHPP adapter, database, FastAPI, or React.

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

## Persistence and schema evolution

- `players` holds stable Hattrick identity metadata, including specialty, nationality and whether the player receives a mother-club bonus.
- `player_snapshots` holds time-specific age, visible skills, stamina, form, experience, loyalty, injury level, cards, TSI, wage, and foreign status.
- `sync_runs` records each manual import's source and outcome.
- `oauth_credentials` contains the single local user's CHPP access token in live mode.
- `oauth_request_states` temporarily stores OAuth request-token state during authorization.
- `training_plans` and related block/assignment tables persist hypothetical manual configuration.
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
- Optimization, transfers, lineup ratings, tactics, wages, and finance projections remain future work.
