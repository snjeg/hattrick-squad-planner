# Hattrick Squad Development Planner

Milestone 4.1 adds plan-bound economy, arena, fixture, attendance, wage, and cash-flow scenarios to the
existing CHPP squad import and manual training simulator. Managers choose every block,
assignment, and financial assumption. The application projects “If I follow this plan,
what happens?” without recommending a strategy.

Milestones 1 through 3 provide CHPP senior-player ingestion, immutable factual snapshots, a verified standalone training engine, and a persistent manual training-cycle simulator. Managers choose every block and assignment; the application projects the question “If I follow this plan, what happens?” without recommending a strategy.

The local development default is mock CHPP XML, so ingestion works without credentials or live Hattrick access. Training calculations consume normalized domain inputs and do not call CHPP, FastAPI, or the frontend.

## Structure

```text
backend/
  alembic/             Managed schema migrations
  app/                 FastAPI app, persistence, and CHPP adapters
  app/training/        Framework-independent training domain engine
  app/simulator/       Week-by-week projection and capacity domain
  app/wage/            Explicitly approximate wage domain
  app/finance/         Framework-independent cash-flow projection domain
  app/attendance/      Table-driven seat demand and gate-revenue domain
  fixtures/chpp/       Fictional CHPP XML used in mock mode
  tests/               Backend, migration, and training unit tests
frontend/
  src/                 React application and tests
docs/architecture.md   Application boundaries and data flow
docs/training-engine.md Formula traceability and training rules
docs/training-simulator.md Manual-plan semantics and capacity assumptions
docs/wage-engine.md     Wage sources, approximation, and uncertainty
docs/finance-projection.md Finance facts, assumptions, and projection semantics
docs/attendance-model.md  Attendance tables, weather uncertainty, and revenue sharing
docs/chpp-player-fields.md CHPP field verification and storage ownership
```

## Backend setup and migrations

Python 3.12 or newer is required.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`. Run the Alembic commands from `backend/`:

```powershell
alembic upgrade head
alembic current
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

The migration chain creates or upgrades the factual squad schema and adds persistent plan,
finance-snapshot, fixture, arena, and scenario-assumption tables through Milestone 4.
Application startup does not create or mutate the schema; run `alembic upgrade head`
before starting it. Tests may continue to create disposable schemas directly.

The API runs at `http://localhost:8000`. SQLite defaults to `backend/data/hattrick_planner.db`; override it with `DATABASE_URL`. Migrations use portable SQLAlchemy operations intended for SQLite and PostgreSQL.

## Frontend setup

Node.js 22 or newer and pnpm are recommended.

```sh
cd frontend
pnpm install
pnpm dev
```

The frontend runs at `http://localhost:5173` and proxies `/api` to FastAPI.

## Manual mock sync

1. Start the backend and frontend with `CHPP_MODE=mock`, the default.
2. Open `http://localhost:5173`.
3. Select **Sync senior squad**.
4. The fictional XML fixture is normalized, persisted, and displayed.
5. Sync again to append another snapshot for each player while retaining identities.

## Manual training plans

Open **Training plans**, create a plan from the latest completed sync, add ordered blocks, configure the training setup, and assign players using Hattrick positions/minutes. Saving an assignment displays the backend-calculated full/partial/osmosis/bonus category. **Simulate plan** shows estimated fractional skills after every block and at plan end.

New blocks default to Playmaking, one week, solid coach, ten assistant levels, 100% intensity, and 10% stamina share. These are editable application assumptions because current club training settings are not imported. Visible skills start at `.00`; projections are never written to factual snapshots.

## Wage and finance scenarios

Each plan captures economy, arena, and fixture facts from the same sync as its starting
squad. In the plan's **Finance projection** section, enter expected home-match revenue and
optionally season-boundary sponsor assumptions, save them, and project weekly cash and
wage pressure across the training blocks.

Imported wages are factual until a projected birthday. Birthday recalculations are
explicitly labeled low-confidence estimates because no complete current official wage
formula is available. Read `docs/wage-engine.md` before using them for decisions. Match
attendance, transfer activity, and post-boundary sponsor income are not invented.

## Live CHPP configuration

Copy `backend/.env.example` to `backend/.env`, set `CHPP_MODE=live`, and provide credentials for an approved CHPP application. Never commit that file or credential values.

The live flow uses CHPP OAuth 1.0a request, authorization, and access-token endpoints and keeps the existing read-only, user-initiated restrictions. The current access-token database storage is plaintext and is **development-only for a single local user**. It must not be used for hosted or multi-user deployment; that requires encrypted secret-at-rest storage or a suitable external credential store.

## Verification

From the repository root with the virtual environment active:

```sh
ruff check backend
mypy --config-file backend/pyproject.toml backend/app
pytest backend
cd frontend
pnpm lint
pnpm test
pnpm build
```

## API endpoints

- `GET /api/health` - service health.
- `GET /api/chpp/status` - mock/live mode and connection status.
- `POST /api/chpp/auth/start` - begin live OAuth authorization.
- `GET /api/chpp/auth/callback` - complete live OAuth authorization.
- `POST /api/chpp/sync` - user-triggered senior squad import.
- `GET /api/squad` - chronologically latest snapshot for each imported player.
- `GET|POST /api/training-plans` - list or create stable-snapshot manual plans.
- `GET|PATCH|DELETE /api/training-plans/{id}` - read, rename/override, or delete a plan.
- `POST|PATCH|DELETE /api/training-plans/{id}/blocks[...]` - add, edit, or remove blocks.
- `PUT /api/training-plans/{id}/blocks/order` - reorder every block deterministically.
- `PUT /api/training-plans/{id}/blocks/{block}/assignments` - replace planned positional exposure.
- `POST /api/training-plans/{id}/simulate` - run the hypothetical week-by-week projection; add `?detailed=true` for weekly output.
- `GET /api/training-plans/{id}/finance` - read plan-bound economy/arena/fixture facts and assumptions.
- `PUT /api/training-plans/{id}/finance/assumptions` - replace explicit scenario assumptions.
- `PUT /api/training-plans/{id}/finance/fixtures/{match_id}` - set fixture weather/revenue assumptions.
- `POST /api/training-plans/{id}/finance/simulate` - project weekly wages and operating cash flow.

The simulator is manual: there is deliberately no optimizer, recommended training cycle,
transfer advice or valuation, lineup engine, tactics model, stadium optimizer, or finance
recommendation. Read `PROJECT_SPEC.md`, `AGENTS.md`, and `DECISIONS.md` before extending
the product.
