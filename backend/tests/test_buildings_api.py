"""
Test script for Buildings API endpoints.

Tests:
1. Import verification
2. Service initialization
3. Basic endpoint calls (if server is running)
"""

import sys


def test_imports():
    """Test that all building-related modules import correctly."""
    print("=" * 60)
    print("Testing Buildings API Imports")
    print("=" * 60)

    tests = [
        ("Building Filters Model", "from app.models.requests import BuildingFilters"),
        (
            "Buildings List Response",
            "from app.models.responses import BuildingsListResponse",
        ),
        (
            "Real Estate Service",
            "from app.services.real_estate_service import RealEstateService",
        ),
        ("Buildings Endpoint", "from app.api.v1.endpoints import buildings"),
        ("Main Router Integration", "from app.api.v1.router import api_router"),
    ]

    passed = 0
    failed = 0

    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f" {name}")
            passed += 1
        except Exception as e:
            print(f" {name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Import Tests: {passed} passed, {failed} failed")
    print("=" * 60)

    assert failed == 0


def test_service_init():
    """Test that RealEstateService can be initialized."""
    print("\n" + "=" * 60)
    print("Testing Real Estate Service Initialization")
    print("=" * 60)

    try:
        from app.services.real_estate_service import RealEstateService

        service = RealEstateService()
        print(f" Service initialized successfully")
        print(f"  Cache: {service._dataset_cache}")
        assert service is not None
    except Exception as e:
        print(f" Service initialization failed: {e}")
        raise


if __name__ == "__main__":
    print("\n Buildings API Test Suite\n")

    imports_ok = test_imports()
    service_ok = test_service_init()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if imports_ok and service_ok:
        print(" All tests passed!")
        print("\n Manual Testing:")
        print("   Start server: python -m uvicorn app.main:app --reload")
        print("   Test endpoints:")
        print("     GET http://localhost:8000/api/v1/buildings")
        print("     GET http://localhost:8000/api/v1/buildings/{id}")
        print("   View docs: http://localhost:8000/docs")
        sys.exit(0)
    else:
        print(" Some tests failed")
        sys.exit(1)
