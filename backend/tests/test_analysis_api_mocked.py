"""Mocked tests for Analysis API and WebSocket progress.

Goal: validate backend behavior (DB persistence, history/delete, WebSocket streaming)
without making any external LLM calls.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.database.models import Base
from app.main import app


@pytest.fixture()
def client_and_sessionmaker(tmp_path, override_dependencies):
    db_file = (tmp_path / "analysis_mock.db").resolve()
    test_db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    override_dependencies(app, {get_db: override_get_db})

    client = TestClient(app)
    try:
        yield client, TestingSessionLocal
    finally:
        client.close()
        Base.metadata.drop_all(bind=engine)


def _poll_until_completed(client: TestClient, run_id: str, timeout_s: float = 2.0):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        r = client.get(f"/api/v1/analysis/{run_id}")
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") in {"completed", "failed"}:
            return last
        time.sleep(0.02)

    assert last is not None
    pytest.fail(
        f"Timed out waiting analysis completion. Last status={last.get('status')}"
    )


def test_analysis_history_and_delete_mocked(client_and_sessionmaker, monkeypatch):
    client, _ = client_and_sessionmaker

    from app.models.responses import Coordinates, BuildingResponse
    from app.services.analysis_service import analysis_service

    # Optional: seed the mock with real query/location from an existing run folder.
    repo_root = Path(__file__).resolve().parents[2]
    metadata_path = (
        repo_root / "runs" / "admin" / "run_20251218_124255_71b2aec2" / "metadata.json"
    )
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        real_query = (
            metadata.get("query") or "Appartamenti a Torino vicino al Politecnico"
        )
        real_location = metadata.get("location_data")
        real_summary = metadata.get("status_message")
    else:
        real_query = "Appartamenti a Torino vicino al Politecnico"
        real_location = [["Torino", 45.07086, 7.685588]]
        real_summary = "OK"

    async def fake_run_analysis(
        run_id: str,
        query: str,
        dataset_key: str = "full",
        map_limit: int = 1000,
        llm_limit: int = 25,
        analysis_mode: str = "agent",
        progress_callback=None,
    ):
        np = pytest.importorskip("numpy")
        return {
            "run_id": run_id,
            "query": query,
            "status": "completed",
            "buildings": [
                BuildingResponse(
                    id="b1",
                    address="Via Roma 1",
                    city="Torino",
                    coordinates=Coordinates(lat=45.07086, lon=7.685588),
                    surface_area=80.0,
                    construction_year="Dal 1991 al 2000",
                    energy_class="A1",
                    score=90.0,
                    is_evaluated=True,
                    meta_building=False,
                )
            ],
            "location": real_location,
            "filters_applied": {"where_clause": "city = 'Torino'"},
            "gemini_responses": {"mock": True, "arr": np.array([1, 2, 3])},
            "broker_summary": real_summary,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        }

    monkeypatch.setattr(analysis_service, "run_analysis", fake_run_analysis)

    response = client.post(
        "/api/v1/analysis",
        json={
            "query": real_query,
            "dataset_key": "full",
            "map_limit": 10,
            "llm_limit": 1,
            "analysis_mode": "agent",
        },
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    results = _poll_until_completed(client, run_id)
    assert results["status"] == "completed"
    assert results["run_id"] == run_id
    assert len(results.get("buildings") or []) == 1
    assert isinstance(results.get("gemini_responses", {}).get("arr"), list)

    history = client.get("/api/v1/analysis/history").json()
    assert isinstance(history, list)
    assert any(item.get("run_id") == run_id for item in history)

    delete_resp = client.delete(f"/api/v1/analysis/{run_id}")
    assert delete_resp.status_code == 204

    after = client.get(f"/api/v1/analysis/{run_id}")
    assert after.status_code == 404


def test_analysis_failed_status_when_service_raises(
    client_and_sessionmaker, monkeypatch
):
    client, _ = client_and_sessionmaker

    from app.services.analysis_service import analysis_service

    async def fake_run_analysis(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(analysis_service, "run_analysis", fake_run_analysis)

    response = client.post(
        "/api/v1/analysis",
        json={
            "query": "Test failure",
            "dataset_key": "full",
            "map_limit": 1,
            "llm_limit": 1,
            "analysis_mode": "agent",
        },
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    results = _poll_until_completed(client, run_id)
    assert results["status"] == "failed"
    assert "Analysis failed" in (results.get("broker_summary") or "")


@pytest.mark.timeout(5)
def test_websocket_progress_streaming_mocked(client_and_sessionmaker, monkeypatch):
    client, _ = client_and_sessionmaker

    from app.models.responses import ProgressUpdate
    from app.services.progress_manager import progress_manager

    async def fake_subscribe(run_id: str):
        yield ProgressUpdate(
            type="progress", progress=10, step="mock", detail="Starting mocked run"
        )

    monkeypatch.setattr(progress_manager, "subscribe", fake_subscribe)

    run_id = "ws_mock_run"

    with client.websocket_connect(f"/api/v1/ws/analysis/{run_id}") as ws:
        msg1 = ws.receive_json()
        assert msg1.get("type") == "progress"
        assert msg1.get("progress") == 10
        assert msg1.get("step") == "mock"

        msg2 = ws.receive_json()
        assert msg2.get("type") == "complete"
        assert msg2.get("run_id") == run_id
        assert (
            msg2.get("results_url") == f"/api/v1/analysis/{run_id}"
        )  # contract in websockets.py
