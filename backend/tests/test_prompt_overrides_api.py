"""Tests for prompt override API.

These tests monkeypatch prompt_config.md location so we don't touch repo files.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.api.deps import get_db
from app.database.models import Base
from app.main import app
from app.services.llm import prompt_loader


@pytest.fixture()
def client_and_db(tmp_path, override_dependencies):
    db_file = (tmp_path / "prompts_api.db").resolve()
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


def test_prompt_overrides_roundtrip(client_and_db, monkeypatch):
    client, tmp_path = client_and_db

    # Force DEBUG=True to allow prompt editing
    from app.core.config import settings
    monkeypatch.setattr(settings, "DEBUG", True)

    # Create config with new system/user structure
    config_path = tmp_path / "prompt_config.md"
    config_path.write_text(
        "## location_agent.system\n"
        "```prompt\n"
        "OLD_SYSTEM\n"
        "```prompt\n"
        "\n"
        "## location_agent.user\n"
        "```prompt\n"
        "OLD_USER\n"
        "```prompt\n",
        encoding="utf-8",
    )

    # Redirect the prompt loader to our temp config file
    monkeypatch.setattr(prompt_loader, "CONFIG_PATH", config_path)
    prompt_loader.reload_prompt_cache()

    resp = client.get("/api/v1/prompts/overrides")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["location_agent"]["system"] == "OLD_SYSTEM"
    assert data["location_agent"]["user"] == "OLD_USER"

    # Test get single system prompt
    resp = client.get("/api/v1/prompts/overrides/location_agent/system")
    assert resp.status_code == 200, resp.text
    assert resp.json()["text"] == "OLD_SYSTEM"

    # Test get single user template
    resp = client.get("/api/v1/prompts/overrides/location_agent/user")
    assert resp.status_code == 200, resp.text
    assert resp.json()["text"] == "OLD_USER"

    # Test update system prompt
    resp = client.put(
        "/api/v1/prompts/overrides/location_agent/system",
        json={"text": "NEW_SYSTEM\nLINE2"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["text"] == "NEW_SYSTEM\nLINE2"

    # Verify the update persisted
    resp = client.get("/api/v1/prompts/overrides/location_agent/system")
    assert resp.status_code == 200, resp.text
    assert resp.json()["text"] == "NEW_SYSTEM\nLINE2"
