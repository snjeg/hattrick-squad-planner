from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.chpp.client import AccessToken, MockCHPPClient, OAuthCHPPClient
from app.config import Settings, get_settings
from app.contribution.types import ContributionValidationError
from app.contribution_services import analyze_plan_player_contributions
from app.database import get_session
from app.finance_services import (
    get_plan_finance,
    run_finance_projection,
    update_fixture_attendance_assumption,
    update_plan_finance_assumptions,
)
from app.models import OAuthCredential, OAuthRequestState
from app.plan_services import (
    PlanNotFoundError,
    PlanValidationError,
    add_training_block,
    create_training_plan,
    delete_training_block,
    delete_training_plan,
    get_training_plan,
    list_training_plans,
    reorder_training_blocks,
    replace_training_assignments,
    run_training_simulation,
    update_training_block,
    update_training_plan,
)
from app.schemas import (
    AuthStartResponse,
    CHPPStatusResponse,
    ContributionAnalysisRequest,
    FinanceAssumptionsUpdate,
    FinanceProjectionResponse,
    FixtureAttendanceUpdate,
    HealthResponse,
    PlanFinanceResponse,
    PlanSquadEvaluationRequest,
    PlanSquadEvaluationResponse,
    PlanTeamRatingRequest,
    PlanTeamRatingResponse,
    PlayerContributionAnalysisResponse,
    SimulationResponse,
    SquadEvaluationCalculateRequest,
    SquadEvaluationResponse,
    SquadResponse,
    SyncResponse,
    TeamRatingCalculateRequest,
    TeamRatingCalculationResponse,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingBlockOrderUpdate,
    TrainingBlockUpdate,
    TrainingPlanCreate,
    TrainingPlanListResponse,
    TrainingPlanResponse,
    TrainingPlanUpdate,
)
from app.services import get_squad, sync_squad
from app.simulator.capacity import CapacityValidationError
from app.squad_evaluation.types import SquadEvaluationValidationError
from app.squad_evaluation_services import evaluate_plan_squad, evaluate_supplied_squad
from app.team_rating.types import TeamRatingValidationError
from app.team_rating_services import evaluate_plan_team_rating, evaluate_supplied_team_rating

SessionDependency = Annotated[Session, Depends(get_session)]


app = FastAPI(title="Hattrick Squad Planner API", version="0.6.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(PlanNotFoundError)
def plan_not_found(_: Request, error: PlanNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(PlanValidationError)
@app.exception_handler(CapacityValidationError)
@app.exception_handler(ContributionValidationError)
@app.exception_handler(TeamRatingValidationError)
@app.exception_handler(SquadEvaluationValidationError)
def invalid_plan(_: Request, error: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


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

        def fetch_own_economy(
            self, team_id: int, access_token: AccessToken | None = None
        ) -> str:
            return live_client.fetch_own_economy(team_id, stored_token)

        def fetch_own_arena(self, access_token: AccessToken | None = None) -> str:
            return live_client.fetch_own_arena(stored_token)

        def fetch_own_matches(
            self, team_id: int, access_token: AccessToken | None = None
        ) -> str:
            return live_client.fetch_own_matches(team_id, stored_token)

    return sync_squad(session, AuthenticatedClient(), "chpp")


@app.get("/api/squad", response_model=SquadResponse)
def squad(session: SessionDependency) -> SquadResponse:
    return get_squad(session)


@app.get("/api/training-plans", response_model=TrainingPlanListResponse)
def training_plans(session: SessionDependency) -> TrainingPlanListResponse:
    return list_training_plans(session)


@app.post(
    "/api/training-plans",
    response_model=TrainingPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    session: SessionDependency, payload: TrainingPlanCreate
) -> TrainingPlanResponse:
    return create_training_plan(session, payload)


@app.get("/api/training-plans/{plan_id}", response_model=TrainingPlanResponse)
def read_plan(session: SessionDependency, plan_id: int) -> TrainingPlanResponse:
    return get_training_plan(session, plan_id)


@app.post(
    "/api/training-plans/{plan_id}/players/{player_id}/contributions",
    response_model=PlayerContributionAnalysisResponse,
)
def analyze_contributions(
    session: SessionDependency,
    plan_id: int,
    player_id: int,
    payload: ContributionAnalysisRequest,
) -> PlayerContributionAnalysisResponse:
    return analyze_plan_player_contributions(session, plan_id, player_id, payload)


@app.post(
    "/api/training-plans/{plan_id}/team-ratings",
    response_model=PlanTeamRatingResponse,
)
def evaluate_team_rating(
    session: SessionDependency, plan_id: int, payload: PlanTeamRatingRequest
) -> PlanTeamRatingResponse:
    return evaluate_plan_team_rating(session, plan_id, payload)


@app.post("/api/team-ratings/calculate", response_model=TeamRatingCalculationResponse)
def calculate_supplied_team_rating(
    payload: TeamRatingCalculateRequest,
) -> TeamRatingCalculationResponse:
    return evaluate_supplied_team_rating(payload)


@app.post("/api/squad-evaluations/calculate", response_model=SquadEvaluationResponse)
def calculate_supplied_squad_evaluation(
    payload: SquadEvaluationCalculateRequest,
) -> SquadEvaluationResponse:
    return evaluate_supplied_squad(payload)


@app.post(
    "/api/training-plans/{plan_id}/squad-evaluation",
    response_model=PlanSquadEvaluationResponse,
)
def calculate_plan_squad_evaluation(
    session: SessionDependency,
    plan_id: int,
    payload: PlanSquadEvaluationRequest,
) -> PlanSquadEvaluationResponse:
    return evaluate_plan_squad(session, plan_id, payload)


@app.patch("/api/training-plans/{plan_id}", response_model=TrainingPlanResponse)
def update_plan(
    session: SessionDependency, plan_id: int, payload: TrainingPlanUpdate
) -> TrainingPlanResponse:
    return update_training_plan(session, plan_id, payload)


@app.delete(
    "/api/training-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_plan(session: SessionDependency, plan_id: int) -> Response:
    delete_training_plan(session, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/api/training-plans/{plan_id}/blocks",
    response_model=TrainingPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_block(
    session: SessionDependency, plan_id: int, payload: TrainingBlockCreate
) -> TrainingPlanResponse:
    return add_training_block(session, plan_id, payload)


@app.patch(
    "/api/training-plans/{plan_id}/blocks/{block_id}",
    response_model=TrainingPlanResponse,
)
def update_block(
    session: SessionDependency,
    plan_id: int,
    block_id: int,
    payload: TrainingBlockUpdate,
) -> TrainingPlanResponse:
    return update_training_block(session, plan_id, block_id, payload)


@app.delete(
    "/api/training-plans/{plan_id}/blocks/{block_id}",
    response_model=TrainingPlanResponse,
)
def delete_block(
    session: SessionDependency, plan_id: int, block_id: int
) -> TrainingPlanResponse:
    return delete_training_block(session, plan_id, block_id)


@app.put(
    "/api/training-plans/{plan_id}/blocks/order",
    response_model=TrainingPlanResponse,
)
def reorder_blocks(
    session: SessionDependency,
    plan_id: int,
    payload: TrainingBlockOrderUpdate,
) -> TrainingPlanResponse:
    return reorder_training_blocks(session, plan_id, payload)


@app.put(
    "/api/training-plans/{plan_id}/blocks/{block_id}/assignments",
    response_model=TrainingPlanResponse,
)
def configure_assignments(
    session: SessionDependency,
    plan_id: int,
    block_id: int,
    payload: TrainingAssignmentsReplace,
) -> TrainingPlanResponse:
    return replace_training_assignments(session, plan_id, block_id, payload)


@app.post(
    "/api/training-plans/{plan_id}/simulate", response_model=SimulationResponse
)
def simulate(
    session: SessionDependency,
    plan_id: int,
    detailed: Annotated[bool, Query()] = False,
) -> SimulationResponse:
    return run_training_simulation(session, plan_id, detailed=detailed)


@app.get(
    "/api/training-plans/{plan_id}/finance", response_model=PlanFinanceResponse
)
def plan_finance(session: SessionDependency, plan_id: int) -> PlanFinanceResponse:
    return get_plan_finance(session, plan_id)


@app.put(
    "/api/training-plans/{plan_id}/finance/assumptions",
    response_model=PlanFinanceResponse,
)
def update_finance_assumptions(
    session: SessionDependency,
    plan_id: int,
    payload: FinanceAssumptionsUpdate,
) -> PlanFinanceResponse:
    return update_plan_finance_assumptions(session, plan_id, payload)


@app.put(
    "/api/training-plans/{plan_id}/finance/fixtures/{match_id}",
    response_model=PlanFinanceResponse,
)
def update_fixture_attendance(
    session: SessionDependency,
    plan_id: int,
    match_id: int,
    payload: FixtureAttendanceUpdate,
) -> PlanFinanceResponse:
    return update_fixture_attendance_assumption(session, plan_id, match_id, payload)


@app.post(
    "/api/training-plans/{plan_id}/finance/simulate",
    response_model=FinanceProjectionResponse,
)
def simulate_finances(
    session: SessionDependency, plan_id: int
) -> FinanceProjectionResponse:
    return run_finance_projection(session, plan_id)
