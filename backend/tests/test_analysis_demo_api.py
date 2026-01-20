"""Tests for demo analysis API (runs/admin artifacts loader).

These tests ensure the demo endpoints work without requiring real LLM calls
and without relying on the repo's actual runs/ folder.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.database.models import Base
from app.main import app


@pytest.fixture()
def client_and_db(tmp_path, override_dependencies):
    db_file = (tmp_path / "demo_api.db").resolve()
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
        yield client, tmp_path
    finally:
        client.close()
        Base.metadata.drop_all(bind=engine)


def test_demo_list_and_start_persists_results(client_and_db, monkeypatch):
    client, tmp_path = client_and_db

    # Create a fake runs/admin/demo folder
    demo_root = tmp_path / "runs" / "admin" / "demo_1"
    demo_root.mkdir(parents=True)

    (demo_root / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "demo_1",
                "timestamp": "2025-12-18T12:46:42.888505",
                "query": "demo query",
                "location_data": [["Piazza Castello, Torino", 45.0706447, 7.6846562]],
                "status_message": "demo summary",
                "results_count": 1,
            }
        ),
        encoding="utf-8",
    )

    (demo_root / "results.csv").write_text(
        '"id";"indirizzo";"numero_civico";"latitudine";"longitudine";"superficie_di_riferimento_mq";"epoca_costruzione";"classe_energetica_ape";"score";"is_evaluated";"meta_immobile"\n'
        '"1";"Via Roma";"10";"45.07086";"7.685588";"80.0";"Dal 1991 al 2000";"A1";"90.0";"True";"False"\n',
        encoding="utf-8",
    )

    (demo_root / "gemini_responses.json").write_text(
        json.dumps(
            {
                "location_extraction": {
                    "prompt": {
                        "system": "SYSTEM",
                        "user": "USER",
                        "full_text": "SYSTEM\n\nUSER",
                    },
                    "response": "ok",
                }
            }
        ),
        encoding="utf-8",
    )

    # Force the endpoint module to treat tmp_path as repo root
    from app.api.v1.endpoints import analysis as analysis_endpoints

    monkeypatch.setattr(analysis_endpoints, "_find_repo_root", lambda start: tmp_path)

    demos = client.get("/api/v1/analysis/demos").json()
    assert any(d.get("demo_id") == "demo_1" for d in demos)

    resp = client.post("/api/v1/analysis/demos/demo_1?limit=1")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    run_id = data["run_id"]

    # Results are persisted and retrievable
    results = client.get(f"/api/v1/analysis/{run_id}").json()
    assert results["run_id"] == run_id
    assert results["status"] == "completed"
    assert results["query"] == "demo query"
    assert len(results.get("buildings") or []) == 1
    assert results["buildings"][0]["city"] == "Torino"

    gemini = results.get("gemini_responses") or {}
    assert "location_extraction" in gemini

    gemini_only = client.get(f"/api/v1/analysis/{run_id}/gemini_responses").json()
    assert "location_extraction" in gemini_only

    steps = client.get(f"/api/v1/analysis/{run_id}/agent_steps").json()
    assert steps["run_id"] == run_id
    assert any(s.get("key") == "location_extraction" for s in steps.get("steps") or [])
    loc_step = next(s for s in steps["steps"] if s.get("key") == "location_extraction")
    assert loc_step["prompt"]["system"] == "SYSTEM"
    assert loc_step["response"] == "ok"

    only_loc = client.get(
        f"/api/v1/analysis/{run_id}/agent_steps?keys=location_extraction&include_raw=true"
    ).json()
    assert len(only_loc.get("steps") or []) == 1
    assert only_loc["steps"][0]["key"] == "location_extraction"
