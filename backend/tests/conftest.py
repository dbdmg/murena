import os
import sys

from contextlib import ExitStack, contextmanager
from typing import Callable, Dict, Iterator

import pytest

# Ensure `backend/` is on sys.path so tests can `import app...`
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


@contextmanager
def temporary_dependency_overrides(
    app, overrides: Dict[Callable, Callable]
) -> Iterator[None]:
    """Temporarily apply FastAPI dependency overrides and restore previous state.

    This prevents test cross-talk when multiple test modules override the same dependency.
    """

    previous = {}
    had_key = {}
    for dep, override in overrides.items():
        if dep in app.dependency_overrides:
            previous[dep] = app.dependency_overrides[dep]
            had_key[dep] = True
        else:
            had_key[dep] = False
        app.dependency_overrides[dep] = override

    try:
        yield
    finally:
        for dep in overrides.keys():
            if had_key.get(dep):
                app.dependency_overrides[dep] = previous[dep]
            else:
                app.dependency_overrides.pop(dep, None)


@pytest.fixture()
def override_dependencies():
    """Fixture to stack multiple temporary dependency overrides safely."""

    stack = ExitStack()

    def apply(app, overrides: Dict[Callable, Callable]) -> None:
        stack.enter_context(temporary_dependency_overrides(app, overrides))

    try:
        yield apply
    finally:
        stack.close()


def pytest_configure(config):
    """Registra i marker personalizzati."""
    config.addinivalue_line(
        "markers", "real_llm: test che usano LLM reali (richiede RUN_REAL_LLM_TESTS=1)"
    )
