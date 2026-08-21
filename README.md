# Hattrick Training Strategy Planner

A local-first planner for building efficient, financially feasible Hattrick senior-team
training cycles. The product has four areas:

- **Squad** — factual CHPP observations;
- **Strategy** — football identity and the source-backed position/skill requirement map;
- **Training Plan** — a manual “If I train this cohort this way, what happens?” sandbox;
- **Finance** — plan-bound cash and wage projections.

Strategy is the core product. Verified contribution, team-rating, squad-evaluation,
roster-scenario and bounded-optimizer engines remain available internally, but are no longer
standalone frontend tools.

## Milestone 9

Milestone 9 resets the product around Strategy and adds a framework-independent Position ×
Skill × Tactical Context Matrix. Direct dots come from the existing pinned Hattrick
Organizer contribution coefficients. Tactic color is a separate official-Rules-backed
overlay and cannot change direct values.

The complete create/edit/assign/simulate/delete plan lifecycle is regression-tested against
the factual squad: Player identities and every PlayerSnapshot row remain unchanged.

See:

- docs/strategy-matrix.md for coefficient, tactic and visualization traceability;
- docs/architecture.md for domain boundaries;
- PROJECT_SPEC.md for the revised product direction;
- DECISIONS.md for durable design decisions.

## Structure

~~~text
backend/
  alembic/              Managed schema migrations
  app/strategy/         Position/skill/tactic matrix domain
  app/training/         Standalone weekly training formula
  app/simulator/        Cohort capacity and week-by-week projection
  app/contribution/     Audited individual contribution primitive
  app/team_rating/      Internal selected-XI sector calculation
  app/squad_evaluation/ Internal bounded whole-squad search
  app/roster_scenario/  Internal checkpoint transition evidence
  app/optimizer/        Retained Milestone 8 bounded optimizer
  app/wage/             Explicitly approximate wage projection
  app/attendance/       Table-driven attendance estimate
  app/finance/          Cash-flow projection
  tests/                Domain, API and migration tests
frontend/src/
  App.tsx               Four-area product navigation
  StrategyWorkspace.tsx Strategy identity and matrix
  TrainingPlans.tsx     Manual training sandbox
  FinanceWorkspace.tsx  Plan-bound financial forecast
~~~

## Backend setup and migrations

Python 3.12 or newer is required.

~~~sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload
~~~

On Windows PowerShell, activate with .\.venv\Scripts\Activate.ps1. Run Alembic from
backend/:

~~~powershell
alembic upgrade head
alembic current
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
~~~

Application startup does not silently create production schema. SQLite defaults to
backend/data/hattrick_planner.db; override it with DATABASE_URL. Migrations remain intended
for SQLite and PostgreSQL.

## Frontend setup

Node.js 22 or newer and pnpm are recommended.

~~~sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
~~~

Vite runs at http://localhost:5173 and proxies /api to FastAPI at
http://localhost:8000.

## Local mock flow

1. Start backend and frontend with CHPP_MODE=mock (the default).
2. Open **Squad** and select **Sync senior squad**.
3. Inspect the appended factual squad observation.
4. Open **Strategy** to select preferred formations and a tactic, then inspect normal or
   alternative individual orders.
5. Open **Training Plan** to create explicit blocks and simulate a hypothetical cohort.
6. Open **Finance** to select a plan horizon and inspect cash feasibility.

## Strategy matrix

POST /api/strategy/matrix accepts a primary tactic and zero or more preferred legal
formations. It returns:

- all seven skills and all 19 supported role/order combinations;
- raw sector coefficients and their sum;
- within-row normalized direct relevance and deterministic one-to-three-dot quantization;
- a separate none/supporting/primary tactic overlay;
- evidence/source labels and explanations;
- the validated formation set and model versions.

Normal adds no overlay. AIM/AOW and Pressing use qualitative Rules evidence. Counter
Attacks preserves the documented two-to-one Passing/Defending input relationship. Long
Shots preserves the documented three-to-one Scoring/Set Pieces relationship. Play
Creatively gets no skill-cell weight because the Rules assign it no tactic skill; specialties
remain a documented non-matrix concern.

Preferences are request/UI state in Milestone 9. Persistence is deferred until team/user
ownership is modeled; no formation is preselected as a universal default.

## Factual and hypothetical data

Manual sync appends PlayerSnapshot observations. Current Squad reads the chronologically
latest snapshot with deterministic tie-breaking. Training plans reference exact starting
snapshots; simulations return projected state without writing it to factual tables.

Deleting a training plan deletes only its hypothetical plan configuration and associations.
It does not delete Player or PlayerSnapshot rows.

## Finance and uncertainty

Finance keeps factual observations, manager assumptions, community estimates and projections
visually and structurally distinct. Imported wages remain factual until a projected birthday;
later wage estimates are explicitly low confidence. Attendance is a traceable community
scenario, not an exact formula. No market prices are invented and no Hattrick transfer action
is performed.

## Live CHPP configuration

Copy backend/.env.example to backend/.env, set CHPP_MODE=live, and provide credentials for an
approved CHPP application. Never commit credential values.

The integration is OAuth/XML only, read-only in scope and manually triggered. The current
plaintext access-token database storage is development-only for one local user. Hosted or
multi-user deployment requires encrypted secret-at-rest storage or an external credential
store.

## Verification

From the repository root:

~~~sh
ruff check backend
mypy --config-file backend/pyproject.toml backend/app
pytest backend
cd backend
alembic upgrade head
alembic downgrade base
alembic upgrade head
cd ../frontend
pnpm lint
pnpm test
pnpm build
~~~

## Product API

- GET /api/health
- GET /api/chpp/status
- POST /api/chpp/auth/start
- GET /api/chpp/auth/callback
- POST /api/chpp/sync
- GET /api/squad
- POST /api/strategy/matrix
- GET|POST /api/training-plans
- GET|PATCH|DELETE /api/training-plans/{id}
- POST|PATCH|DELETE /api/training-plans/{id}/blocks and related block routes
- PUT /api/training-plans/{id}/blocks/{block}/assignments
- POST /api/training-plans/{id}/simulate
- GET /api/training-plans/{id}/finance
- PUT /api/training-plans/{id}/finance/assumptions
- PUT /api/training-plans/{id}/finance/fixtures/{match_id}
- POST /api/training-plans/{id}/finance/simulate

Lower-level contribution, team-rating, squad-evaluation, roster-scenario and optimizer routes
remain backward-compatible internal capabilities. They are intentionally absent from primary
navigation and should be composed by future Strategy work rather than re-exposed as separate
manager workspaces.
