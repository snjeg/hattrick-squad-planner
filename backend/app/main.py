from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.chpp.client import AccessToken, MockCHPPClient, OAuthCHPPClient
from app.config import Settings, get_settings
from app.database import create_schema, get_session
from app.models import OAuthCredential, OAuthRequestState
from app.schemas import (
    AuthStartResponse,
    CHPPStatusResponse,
    HealthResponse,
    SquadResponse,
    SyncResponse,
)
from app.services import get_squad, sync_squad

SessionDependency = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_schema()
    yield


app = FastAPI(title="Hattrick Squad Planner API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _live_client(settings: Settings) -> OAuthCHPPClient:
    if not settings.chpp_consumer_key or not settings.chpp_consumer_secret:
        raise HTTPException(status_code=503, detail="CHPP consumer credentials are not configured")
    return OAuthCHPPClient(
        settings.chpp_consumer_key, settings.chpp_consumer_secret, settings.chpp_players_version
    )


def _callback_with_state(callback_url: str, state: str) -> str:
    parts = urlsplit(callback_url)
    query = dict(parse_qsl(parts.query))
    query["state"] = state
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/chpp/status", response_model=CHPPStatusResponse)
def chpp_status(session: SessionDependency) -> CHPPStatusResponse:
    connected = settings.chpp_mode == "mock" or session.get(OAuthCredential, 1) is not None
    return CHPPStatusResponse(mode=settings.chpp_mode, connected=connected)


@app.post("/api/chpp/auth/start", response_model=AuthStartResponse)
def start_chpp_auth(session: SessionDependency) -> AuthStartResponse:
    if settings.chpp_mode == "mock":
        return AuthStartResponse(authorization_url=None, state=None)
    state = uuid4().hex
    request = _live_client(settings).begin_authorization(
        _callback_with_state(settings.chpp_callback_url, state)
    )
    session.add(
        OAuthRequestState(
            state=state,
            request_token=request.token,
            request_token_secret=request.secret,
        )
    )
    session.commit()
    return AuthStartResponse(authorization_url=request.authorization_url, state=state)


@app.get("/api/chpp/auth/callback")
def complete_chpp_auth(
    session: SessionDependency,
    state: Annotated[str, Query(min_length=16)],
    oauth_token: str,
    oauth_verifier: str,
) -> RedirectResponse:
    request = session.get(OAuthRequestState, state)
    if request is None or request.request_token != oauth_token:
        raise HTTPException(status_code=400, detail="Invalid or expired CHPP authorization state")
    access = _live_client(settings).complete_authorization(
        request.request_token, request.request_token_secret, oauth_verifier
    )
    credential = session.get(OAuthCredential, 1)
    if credential is None:
        credential = OAuthCredential(
            id=1, access_token=access.token, access_token_secret=access.secret
        )
        session.add(credential)
    else:
        credential.access_token = access.token
        credential.access_token_secret = access.secret
    session.delete(request)
    session.commit()
    return RedirectResponse(f"{settings.frontend_origin}/?connected=1")


@app.post("/api/chpp/sync", response_model=SyncResponse)
def run_chpp_sync(session: SessionDependency) -> SyncResponse:
    if settings.chpp_mode == "mock":
        client = MockCHPPClient(settings.chpp_mock_fixture)
        return sync_squad(session, client, "mock")

    credential = session.get(OAuthCredential, 1)
    if credential is None:
        raise HTTPException(status_code=401, detail="Connect CHPP before syncing")
    live_client = _live_client(settings)
    stored_token = AccessToken(credential.access_token, credential.access_token_secret)

    class AuthenticatedClient:
        def fetch_own_senior_players(self, access_token: AccessToken | None = None) -> str:
            return live_client.fetch_own_senior_players(stored_token)

    return sync_squad(session, AuthenticatedClient(), "chpp")


@app.get("/api/squad", response_model=SquadResponse)
def squad(session: SessionDependency) -> SquadResponse:
    return get_squad(session)
