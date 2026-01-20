"""
Comprehensive test suite for database repositories.

Tests:
- Database models
- Base repository CRUD operations
- User repository operations
- Run repository operations
- Feedback repository operations
"""

import sys
import os

# Imports are configured via tests/conftest.py

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models and repositories
from app.database.models import Base, User, Run, Feedback
from app.repositories import UserRepository, RunRepository, FeedbackRepository


def create_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_user_repository():
    """Test UserRepository operations."""
    print("\n" + "=" * 60)
    print("Testing UserRepository")
    print("=" * 60)

    db = create_test_db()
    repo = UserRepository(db)

    # Test create
    user = repo.create_user("testuser", "hashed_password_123", "test@example.com")
    print(f"✓ Created user: {user.username}")
    assert user.id is not None

    # Test get by username
    found = repo.get_by_username("testuser")
    print(f"✓ Found user by username: {found.username}")
    assert found.id == user.id

    # Test get by email
    found = repo.get_by_email("test@example.com")
    print(f"✓ Found user by email: {found.email}")
    assert found.id == user.id

    # Test uniqueness check
    assert repo.verify_unique_username("newuser") == True
    assert repo.verify_unique_username("testuser") == False
    print("✓ Uniqueness verification works")

    # Test update
    updated = repo.update(user.id, email="newemail@example.com")
    print(f"✓ Updated user email: {updated.email}")
    assert updated.email == "newemail@example.com"

    # Test get_all
    users = repo.get_all()
    print(f"✓ Get all users: {len(users)} users")
    assert len(users) == 1

    db.close()
    print("\n✅ All UserRepository tests passed!")


def test_run_repository():
    """Test RunRepository operations."""
    print("\n" + "=" * 60)
    print("Testing RunRepository")
    print("=" * 60)

    db = create_test_db()
    user_repo = UserRepository(db)
    run_repo = RunRepository(db)

    # Create test user
    user = user_repo.create_user("testuser", "pass123")

    # Test create run
    run = run_repo.create_run(
        run_id="run_test_001",
        query="Appartamenti a Roma",
        user_id=user.id,
        dataset_key="full",
        analysis_mode="agent",
    )
    print(f"✓ Created run: {run.run_id}")
    assert run.id is not None
    assert run.status == "processing"

    # Test get by run_id
    found = run_repo.get_by_run_id("run_test_001")
    print(f"✓ Found run by run_id: {found.run_id}")
    assert found.id == run.id

    # Test update status
    updated = run_repo.update_status(
        "run_test_001",
        status="completed",
        status_message="Analysis completed successfully",
    )
    print(f"✓ Updated run status: {updated.status}")
    assert updated.status == "completed"
    assert updated.completed_at is not None

    # Create more runs for testing
    run_repo.create_run("run_test_002", "Case a Milano", user.id)
    run_repo.create_run("run_test_003", "Uffici a Torino", user.id)

    # Test get user runs
    user_runs = run_repo.get_user_runs(user.id, limit=10)
    print(f"✓ Get user runs: {len(user_runs)} runs")
    assert len(user_runs) == 3

    # Test save complete results
    complete = run_repo.save_complete_results(
        "run_test_002",
        results={"buildings": [], "count": 0},
        gemini_responses={"location": "Milano"},
        location_data=[["Milano", 45.46, 9.19]],
        status_message="Completed",
        results_count=0,
    )
    print(f"✓ Saved complete results for run: {complete.run_id}")
    assert complete.status == "completed"
    assert complete.results_count == 0

    # Test get recent runs
    recent = run_repo.get_recent_runs(limit=5)
    print(f"✓ Get recent runs: {len(recent)} runs")
    assert len(recent) == 3

    db.close()
    print("\n✅ All RunRepository tests passed!")


def test_feedback_repository():
    """Test FeedbackRepository operations."""
    print("\n" + "=" * 60)
    print("Testing FeedbackRepository")
    print("=" * 60)

    db = create_test_db()
    feedback_repo = FeedbackRepository(db)

    # Create test run (minimal)
    run = Run(run_id="run_test_001", query="Test query")
    db.add(run)
    db.commit()

    # Test create feedback
    feedback1 = feedback_repo.create_feedback(
        run_id="run_test_001",
        building_id="building_123",
        rating=5,
        comment="Excellent location!",
        helpful=1,
    )
    print(f"✓ Created feedback: rating={feedback1.rating}")
    assert feedback1.id is not None

    # Create more feedback
    feedback2 = feedback_repo.create_feedback(
        "run_test_001", "building_456", 4, "Good value"
    )
    feedback3 = feedback_repo.create_feedback(
        "run_test_001", "building_123", 3, "Average"
    )

    # Test get by building
    building_feedback = feedback_repo.get_by_building("building_123")
    print(f"✓ Get feedback by building: {len(building_feedback)} feedbacks")
    assert len(building_feedback) == 2

    # Test get by run
    run_feedback = feedback_repo.get_by_run("run_test_001")
    print(f"✓ Get feedback by run: {len(run_feedback)} feedbacks")
    assert len(run_feedback) == 3

    # Test update feedback
    updated = feedback_repo.update_feedback(
        feedback1.id,
        rating=4,
        comment="Updated comment",
        e1="Evaluation 1",
        e2="Evaluation 2",
    )
    print(f"✓ Updated feedback: new rating={updated.rating}")
    assert updated.rating == 4
    assert updated.feedback_e1 == "Evaluation 1"

    # Test average rating
    avg = feedback_repo.get_building_rating_average("building_123")
    print(f"✓ Average rating for building_123: {avg:.2f}")
    assert avg == (4 + 3) / 2  # (updated feedback1 + feedback3) / 2

    db.close()
    print("\n✅ All FeedbackRepository tests passed!")


def run_all_tests():
    """Run all repository tests."""
    print("\n" + "=" * 60)
    print("🧪 Database Repository Test Suite")
    print("=" * 60)

    try:
        test_user_repository()
        test_run_repository()
        test_feedback_repository()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nRepository layer is fully functional:")
        print("  ✓ SQLAlchemy models working")
        print("  ✓ Base repository CRUD operations")
        print("  ✓ User repository operations")
        print("  ✓ Run repository operations")
        print("  ✓ Feedback repository operations")
        print("\n🎉 Phase 2.3 implementation complete!")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
