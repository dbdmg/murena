"""
Integration tests for Phase 2.5.
Tests Authentication, Analysis flow, and Database persistence.
"""

import sys
import os
import pytest
from contextlib import ExitStack
from fastapi.testclient import TestClient

from pathlib import Path

# Imports are configured via tests/conftest.py

from app.main import app
from app.api.deps import get_db
from app.database.connection import SessionLocal, init_db
from app.database.models import Base
from app.core import security

from tests.conftest import temporary_dependency_overrides

client: TestClient | None = None
_override_stack: ExitStack | None = None

# Override database dependency for tests (optional, but good practice)
# For this integration test, we might use the actual dev DB or a test DB.
# Given we want to test "migration" success, using a separate test.db is safer.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_db_file = (Path(__file__).parent / "test_integration.db").resolve()
TEST_DATABASE_URL = f"sqlite:///{_db_file.as_posix()}"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def setup_module(module):
    """Setup test database."""
    Base.metadata.create_all(bind=engine)

    global _override_stack
    global client
    _override_stack = ExitStack()
    _override_stack.enter_context(temporary_dependency_overrides(app, {get_db: override_get_db}))
    client = TestClient(app)

    # Create admin user
    db = TestingSessionLocal()
    if not db.query(Base.metadata.tables["users"]).first():
        from app.repositories import UserRepository

        repo = UserRepository(db)
        repo.create_user(
            username="admin",
            password_hash=security.get_password_hash("admin123"),
            email="admin@test.com",
        )
    db.close()


def teardown_module(module):
    """Cleanup test database."""
    global _override_stack
    global client

    if client is not None:
        client.close()
        client = None

    if _override_stack is not None:
        _override_stack.close()
        _override_stack = None

    Base.metadata.drop_all(bind=engine)
    # os.remove("./test_integration.db")


def test_1_health_check():
    """Test health check endpoint."""
    assert client is not None
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_2_auth_flow():
    """Test Login -> Me -> Refresh flow."""
    assert client is not None
    # 1. Login
    login_data = {"username": "admin", "password": "admin123"}
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    token_data = response.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 2. Get Me
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["username"] == "admin"

    # 3. Refresh Token
    import time

    time.sleep(1.1)  # Ensure token exp changes (JWT has second precision)
    response = client.post("/api/v1/auth/refresh", headers=headers)
    assert response.status_code == 200
    new_token_data = response.json()
    assert "access_token" in new_token_data
    assert new_token_data["access_token"] != token


def test_3_register_flow():
    """Test Registration -> Login."""
    assert client is not None
    # 1. Register
    reg_data = {
        "username": "newuser",
        "password": "password123",
        "email": "new@test.com",
    }
    response = client.post("/api/v1/auth/register", json=reg_data)
    assert response.status_code == 200
    assert response.json()["username"] == "newuser"

    # 2. Fail duplicate
    response = client.post("/api/v1/auth/register", json=reg_data)
    assert response.status_code == 400


def test_4_analysis_integration():
    """Test Analysis start -> persistence -> retrieval using a mocked analysis service."""
    import time
    from datetime import datetime

    assert client is not None

    # Monkeypatch the global analysis_service to avoid real LLM calls
    from app.services.analysis_service import analysis_service
    from app.models.responses import Coordinates, BuildingResponse

    async def fake_run_analysis(
        run_id: str,
        query: str,
        dataset_key: str = "full",
        map_limit: int = 1000,
        llm_limit: int = 25,
        analysis_mode: str = "agent",
        progress_callback=None,
    ):
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
            "location": [["Torino", 45.07086, 7.685588]],
            "filters_applied": {"where_clause": "city = 'Torino'"},
            "gemini_responses": {"mock": True},
            "broker_summary": "OK",
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        }

    original = analysis_service.run_analysis
    analysis_service.run_analysis = fake_run_analysis
    try:
        payload = {
            "query": "Appartamenti a Torino vicino al Politecnico",
            "dataset_key": "full",
            "map_limit": 10,
            "llm_limit": 1,
            "analysis_mode": "agent",
        }
        response = client.post("/api/v1/analysis", json=payload)
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]

        # Poll until the background task persists results
        last = None
        for _ in range(30):
            r = client.get(f"/api/v1/analysis/{run_id}")
            assert r.status_code == 200, r.text
            last = r.json()
            if last.get("status") == "completed" and (last.get("buildings") or []):
                break
            time.sleep(0.05)

        assert last is not None
        assert last["run_id"] == run_id
        assert last["status"] == "completed"
        assert len(last["buildings"]) == 1
        assert last["buildings"][0]["city"] == "Torino"

        # Verify it's really in the DB
        db = TestingSessionLocal()
        from app.repositories import RunRepository

        run = RunRepository(db).get_by_run_id(run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.results_count == 1
        db.close()
    finally:
        analysis_service.run_analysis = original


if __name__ == "__main__":
    # Run with python backend/test_integration.py
    try:
        setup_module(None)
        print("✅ Setup complete")

        test_1_health_check()
        print("✅ Health check passed")

        test_2_auth_flow()
        print("✅ Auth flow passed")

        test_3_register_flow()
        print("✅ Register flow passed")

        print("\n🎉 All integration tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        teardown_module(None)
