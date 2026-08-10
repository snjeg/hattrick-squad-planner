from fastapi.testclient import TestClient


def test_mock_status_sync_and_squad_flow(client: TestClient) -> None:
    status = client.get("/api/chpp/status")
    assert status.status_code == 200
    assert status.json() == {"mode": "mock", "connected": True}

    before = client.get("/api/squad")
    assert before.status_code == 200
    assert before.json()["players"] == []

    sync = client.post("/api/chpp/sync")
    assert sync.status_code == 200
    assert sync.json()["imported_players"] == 3

    after = client.get("/api/squad")
    assert after.status_code == 200
    body = after.json()
    assert len(body["players"]) == 3
    assert body["last_synced_at"] is not None
    assert {
        "player",
        "age_years",
        "age_days",
        "goalkeeper",
        "defending",
        "playmaking",
        "winger",
        "passing",
        "scoring",
        "set_pieces",
        "tsi",
        "wage",
        "is_foreign",
        "specialty",
    }.issubset(body["players"][0])


def test_optimizer_route_validates_whole_squad_scope(client: TestClient) -> None:
    assert client.post("/api/chpp/sync").status_code == 200
    created = client.post("/api/training-plans", json={"name": "Optimizer route"})
    assert created.status_code == 201
    plan = created.json()
    response = client.post(
        f"/api/training-plans/{plan['id']}/optimize",
        json={
            "members": [
                {"player_id": item["player_id"], "planning_role": "rotation"}
                for item in plan["players"]
            ],
            "objective_mode": "balanced",
            "context": {
                "team_spirit": 5.5,
                "confidence": 5,
                "coach_style": 0,
                "attitude": "normal",
                "location": "away",
                "tactic": "normal",
                "weather": "overcast",
            },
        },
    )
    assert response.status_code == 422
    assert "at least eleven" in response.json()["detail"]
