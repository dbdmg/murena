"""Quick import test for critical backend modules"""

import sys
import traceback

import pytest


CRITICAL_IMPORTS = [
    ("app.core.config", "Core Config"),
    ("app.core.constants", "Constants"),
    ("app.models.requests", "Request Models"),
    ("app.models.responses", "Response Models"),
    ("app.api.v1.router", "API Router"),
    ("app.api.v1.endpoints.analysis", "Analysis Endpoint"),
    ("app.services.analysis_service", "Analysis Service"),
    ("app.services.llm.agents.graph_agent", "Graph Agent"),
    ("app.data.loaders", "Data Loaders"),
]


@pytest.mark.parametrize("module_name,description", CRITICAL_IMPORTS)
def test_import(module_name: str, description: str):
    """Quick check: importing critical modules should not raise."""
    try:
        __import__(module_name)
    except Exception as e:
        traceback.print_exc()
        raise AssertionError(
            f"Import failed for {description} ({module_name}): {e}"
        ) from e


if __name__ == "__main__":
    print("=" * 60)
    print("Quick Import Test - Critical Modules")
    print("=" * 60)

    results = []
    for module_name, description in CRITICAL_IMPORTS:
        print(f"\nTesting: {description}")
        try:
            __import__(module_name)
            print(f" {description}")
            result = True
        except Exception as e:
            print(f" {description}")
            print(f"  Error: {e}")
            traceback.print_exc()
            result = False
        results.append((description, result))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for description, result in results:
        status = "" if result else ""
        print(f"{status} {description}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n All critical imports successful!")
        sys.exit(0)
    else:
        print(f"\n  {total - passed} import(s) failed")
        sys.exit(1)
