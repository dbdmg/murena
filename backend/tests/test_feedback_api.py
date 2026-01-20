"""Tests for app-level feedback API."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.database.models import Base
from app.repositories import RunRepository
from app.main import app


@pytest.fixture()
def client_and_db(tmp_path, override_dependencies):
    db_file = (tmp_path / "feedback_api.db").resolve()
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


def test_app_feedback_create_and_list(client_and_db):
    client, SessionLocal = client_and_db

    # Create a run directly (avoid background analysis)
    with SessionLocal() as db:
        RunRepository(db).create_run(
            run_id="run_fb_1",
            query="demo",
            user_id=None,
            dataset_key="full",
            analysis_mode="demo",
        )

    payload = {
        "query": {"corrispondenza_query": 4, "ambiguita_prompt": 2},
        "dati_mancanti": {"assenza_dati_difficolta": 3},
    }

    resp = client.post(
        "/api/v1/feedback/app",
        json={
            "run_id": "run_fb_1",
            "payload": payload,
            "rating": 4,
            "comment": "note",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["run_id"] == "run_fb_1"
    assert created["rating"] == 4
    assert created["payload"] == payload
    assert created["comment"] == "note"

    listed = client.get("/api/v1/feedback/app?run_id=run_fb_1&limit=50").json()
    assert isinstance(listed, list)
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_app_feedback_requires_valid_run(client_and_db):
    client, _ = client_and_db

    resp = client.post(
        "/api/v1/feedback/app",
        json={"run_id": "missing", "payload": {"x": 1}},
    )
    assert resp.status_code == 404
