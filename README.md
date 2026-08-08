# Hattrick Squad Development Planner

Milestone 1 provides a React/TypeScript squad view backed by FastAPI, SQLAlchemy, and SQLite. A user manually imports their own senior squad through a CHPP adapter; player identities are normalized and each successful sync adds immutable historical snapshots.

The local development default is mock CHPP XML, so the complete ingestion flow works without credentials or live Hattrick access.

## Structure

```text
backend/
  app/                 FastAPI app, persistence, CHPP adapters, normalization
  fixtures/chpp/       Fictional CHPP XML used in mock mode
  tests/               Backend unit and API tests
frontend/
  src/                 React application and tests
docs/architecture.md   Milestone 1 architecture and data flow
```

## Backend setup

Python 3.12 or newer is required.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
uvicorn app.main:app --app-dir backend --reload
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`.

The API runs at `http://localhost:8000`. SQLite data is created under `backend/data/` when the server is started from the backend directory; override this with `DATABASE_URL` when needed.

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
5. Sync again to append another snapshot for each player while retaining the same identities.

## Live CHPP configuration

Copy `backend/.env.example` to `backend/.env`, set `CHPP_MODE=live`, and provide credentials for an approved CHPP application. Never commit that file or credential values.

The live flow uses CHPP OAuth 1.0a request, authorization, and access-token endpoints. The application requests only the normal read access represented by its approved CHPP registration. Squad downloads occur only when the user selects the sync action; there is no scheduled or background sync.

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
- `GET /api/squad` - latest snapshot for each imported player.

Read `PROJECT_SPEC.md`, `AGENTS.md`, and `DECISIONS.md` before extending the product beyond Milestone 1.
