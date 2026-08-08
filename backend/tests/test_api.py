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
