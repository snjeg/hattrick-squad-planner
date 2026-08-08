# Milestone 1 architecture

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
      +----> Player identity (insert or update factual identity fields)
      |
      +----> PlayerSnapshot (always append)
      |
      v
SQLite through SQLAlchemy
      |
      v
Latest-snapshot query ----> React squad table
```

Raw CHPP XML does not cross the adapter/normalizer boundary. Later engines should consume normalized domain data or their own explicit projections.

## Persistence

- `players` holds stable Hattrick identity and current identity metadata.
- `player_snapshots` holds time-specific age, visible skills, TSI, wage, and foreign status.
- `sync_runs` records the outcome and source of each manual import.
- `oauth_credentials` contains the single local user's CHPP access token in live mode.
- `oauth_request_states` temporarily stores OAuth request-token state during authorization.

Snapshot rows are never updated by the application. Repeated observations append rows and the squad endpoint selects the newest snapshot per identity.

All schema columns use SQLAlchemy types that work with SQLite and PostgreSQL. Milestone 1 creates the development schema directly; a migration tool is required before managed deployment.

## CHPP boundaries

The integration uses only CHPP OAuth and XML endpoints. It does not accept Hattrick passwords, scrape HTML, schedule downloads, submit match orders, or automate transfers.

Mock mode is the development default. Its fictional XML passes through exactly the same parser and persistence service as live data.

## Known Milestone 1 limits

- Live CHPP behavior requires credentials for an approved application and cannot be exercised by the test suite.
- OAuth access tokens are stored in the local database without application-level encryption. Hosted use requires secret-at-rest protection and a credential-storage decision.
- Specialty remains a numeric CHPP value. Human-readable labels should be added only after the code mapping is verified from an authoritative source.
- The table displays the latest observation only; historical exploration belongs to a later milestone.
