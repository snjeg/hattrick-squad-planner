# Architecture through Milestone 2

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

## Persistence and schema evolution

- `players` holds stable Hattrick identity metadata, including specialty, nationality and whether the player receives a mother-club bonus.
- `player_snapshots` holds time-specific age, visible skills, stamina, form, experience, loyalty, injury level, cards, TSI, wage, and foreign status.
- `sync_runs` records each manual import's source and outcome.
- `oauth_credentials` contains the single local user's CHPP access token in live mode.
- `oauth_request_states` temporarily stores OAuth request-token state during authorization.

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

The calculation is deliberately a domain service, not an API route. It is ready for later week-by-week simulation without yet persisting estimated subskills or introducing optimization.

## CHPP boundaries and credential safety

The integration uses only CHPP OAuth and XML endpoints. It does not accept Hattrick passwords, scrape HTML, schedule downloads, submit match orders, or automate transfers. Mock mode remains the default and follows the same parser and persistence path as live data.

Plaintext OAuth-token storage exists only to support single-user local development. It is forbidden for hosted or multi-user deployment; hosted work requires a separate encrypted credential-store design.

## Current limits

- Live CHPP behavior requires approved application credentials and manual validation.
- The squad-list response reports the mother-club bonus but not the mother club's team identity; HO obtains that identity from a separate player-details response.
- Specialty remains a numeric CHPP value until its labels are verified from an authoritative source.
- Exact fractional skills are calculation inputs/results only and are not inferred or persisted.
- Match-minute reconstruction, multi-week simulation, optimization, transfers, lineup ratings, tactics, finance projections, and training UI remain future work.
