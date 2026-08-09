from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.chpp.client import AccessToken, MockCHPPClient
from app.finance_services import (
    get_plan_finance,
    run_finance_projection,
    update_plan_finance_assumptions,
)
from app.models import FinanceSnapshot, FixtureSnapshot, PlayerSnapshot
from app.plan_services import add_training_block, create_training_plan
from app.schemas import (
    FinanceAssumptionsUpdate,
    TrainingBlockCreate,
    TrainingPlanCreate,
)
from app.services import sync_squad
from app.training.types import TrainingType

FIXTURES = Path(__file__).parents[1] / "fixtures" / "chpp"


class ChangedEconomyClient(MockCHPPClient):
    def fetch_own_economy(self, team_id: int, access_token: AccessToken | None = None) -> str:
        return (
            super().fetch_own_economy(team_id).replace("<Cash>850000</Cash>", "<Cash>975000</Cash>")
        )


def finance_plan(session: Session, *, weeks: int = 3) -> int:
    sync_squad(session, MockCHPPClient(FIXTURES / "players.xml"), "mock")
    plan = create_training_plan(session, TrainingPlanCreate(name="Finance scenario"))
    add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=weeks),
    )
    return plan.id


def test_plan_keeps_original_finance_snapshot_after_later_sync(session: Session) -> None:
    plan_id = finance_plan(session)
    original = get_plan_finance(session, plan_id)

    sync_squad(session, ChangedEconomyClient(FIXTURES / "players.xml"), "mock")
    unchanged = get_plan_finance(session, plan_id)
    newer = create_training_plan(session, TrainingPlanCreate(name="New facts"))
    newer_finance = get_plan_finance(session, newer.id)

    assert original.factual is not None
    assert unchanged.factual is not None
    assert newer_finance.factual is not None
    assert unchanged.factual.snapshot_id == original.factual.snapshot_id
    assert unchanged.factual.cash_balance == 850_000
    assert newer_finance.factual.cash_balance == 975_000


def test_projection_uses_only_home_fixtures_for_assumed_income(session: Session) -> None:
    plan_id = finance_plan(session, weeks=3)
    update_plan_finance_assumptions(
        session,
        plan_id,
        FinanceAssumptionsUpdate(expected_home_match_revenue=40_000),
    )

    projection = run_finance_projection(session, plan_id)

    assert [row.match_income for row in projection.weekly_rows] == [40_000, 0, 40_000]
    assert projection.weekly_rows[0].home_fixture_ids == [700001]
    assert projection.weekly_rows[1].home_fixture_ids == []


def test_balance_dependent_financial_income_is_not_extrapolated(
    session: Session,
) -> None:
    plan_id = finance_plan(session, weeks=2)

    projection = run_finance_projection(session, plan_id)

    assert [row.fixed_costs for row in projection.weekly_rows] == [42_500, 42_500]
    assert [row.operating_cash_flow for row in projection.weekly_rows] == [
        -37_860,
        -37_860,
    ]
    assert any("balance-dependent" in note for note in projection.uncertainty_notes)


def test_projection_is_deterministic_and_never_mutates_facts(session: Session) -> None:
    plan_id = finance_plan(session, weeks=2)
    finance_before = session.scalar(select(func.count(FinanceSnapshot.id)))
    players_before = session.scalar(select(func.count(PlayerSnapshot.id)))

    first = run_finance_projection(session, plan_id)
    second = run_finance_projection(session, plan_id)

    assert first == second
    assert session.scalar(select(func.count(FinanceSnapshot.id))) == finance_before
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == players_before


def test_finance_rest_endpoints_round_trip_assumptions_and_projection(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id = finance_plan(session, weeks=2)

    facts = client.get(f"/api/training-plans/{plan_id}/finance")
    assert facts.status_code == 200
    assert facts.json()["factual"]["cash_balance"] == 850_000
    assert facts.json()["wage_model_quality"] == "approximate-low-confidence"

    saved = client.put(
        f"/api/training-plans/{plan_id}/finance/assumptions",
        json={
            "expected_home_match_revenue": 35_000,
            "weeks_until_season_boundary": 1,
            "sponsor_income_after_boundary": 50_000,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["assumptions"]["expected_home_match_revenue"] == 35_000

    projected = client.post(f"/api/training-plans/{plan_id}/finance/simulate")
    assert projected.status_code == 200
    assert projected.json()["weekly_rows"][1]["sponsor_income"] == 50_000


def test_finance_rest_endpoint_rejects_negative_assumptions(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id = finance_plan(session)

    response = client.put(
        f"/api/training-plans/{plan_id}/finance/assumptions",
        json={"expected_home_match_revenue": -1},
    )

    assert response.status_code == 422


def test_fixture_weather_enables_attendance_estimate_and_finance_priority(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id = finance_plan(session, weeks=2)

    initial = client.get(f"/api/training-plans/{plan_id}/finance").json()
    home = next(item for item in initial["fixtures"] if item["match_id"] == 700001)
    assert home["attendance_estimate"] is None
    assert set(home["weather_scenarios"]) == {
        "rain",
        "overcast",
        "partly_cloudy",
        "sunny",
    }

    saved = client.put(
        f"/api/training-plans/{plan_id}/finance/fixtures/700001",
        json={"weather_override": "rain", "manual_revenue_override": None},
    )
    assert saved.status_code == 200
    estimate = next(item for item in saved.json()["fixtures"] if item["match_id"] == 700001)[
        "attendance_estimate"
    ]
    assert estimate["weather"] == "rain"
    assert estimate["quality"] == "approximate-low-confidence"

    projection = client.post(f"/api/training-plans/{plan_id}/finance/simulate").json()
    assert projection["weekly_rows"][0]["match_income"] == estimate["club_revenue"]
    assert projection["weekly_rows"][0]["match_revenue_sources"] == {"700001": "attendance_model"}


def test_away_fixture_exposes_missing_host_facts_and_manual_fallback(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id = finance_plan(session, weeks=3)

    finance = client.get(f"/api/training-plans/{plan_id}/finance").json()
    away = next(item for item in finance["fixtures"] if item["match_id"] == 700002)

    assert away["attendance_model_status"] == "unsupported_away_host_facts"
    assert away["attendance_estimate"] is None
    assert away["weather_scenarios"] == {}
    assert "host club's supporter" in away["attendance_uncertainty_notes"][0]


def test_unresolved_away_shared_gate_is_called_out_in_projection(
    session: Session,
) -> None:
    plan_id = finance_plan(session, weeks=3)
    plan_finance = get_plan_finance(session, plan_id)
    assert plan_finance.factual is not None
    away = session.scalar(
        select(FixtureSnapshot).where(
            FixtureSnapshot.sync_run_id == plan_finance.factual.sync_run_id,
            FixtureSnapshot.match_id == 700002,
        )
    )
    assert away is not None
    away.match_type = 4
    session.commit()

    projection = run_finance_projection(session, plan_id)

    assert projection.weekly_rows[1].match_income == 0
    assert any(
        "Away cup, qualifier, or friendly gate income is excluded" in note
        for note in projection.uncertainty_notes
    )


def test_manual_fixture_revenue_beats_attendance_estimate(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id = finance_plan(session, weeks=2)
    client.put(
        f"/api/training-plans/{plan_id}/finance/fixtures/700001",
        json={"weather_override": "sunny", "manual_revenue_override": 12345},
    )

    projection = client.post(f"/api/training-plans/{plan_id}/finance/simulate").json()
    assert projection["weekly_rows"][0]["match_income"] == 12345
    assert projection["weekly_rows"][0]["match_revenue_sources"] == {
        "700001": "manual_fixture_override"
    }
