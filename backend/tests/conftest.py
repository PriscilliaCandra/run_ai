"""
Shared pytest fixtures for the backend test suite.

Test isolation strategy
------------------------
1. DATABASE_URL is redirected to a private temporary SQLite file *before* any
   `app.*` module is imported (including via other conftest-level imports),
   so the module-level SQLAlchemy engine created in app/database.py is bound
   to the temp file and never touches the real running_research.db used by
   the running application. GEMINI_API_KEY / OPENAI_API_KEY are also forced
   to empty so tests behave the same regardless of the host machine's real
   .env / shell environment.
2. `app.models` is imported eagerly (see bottom of the env-setup block below)
   so every ORM table is registered on `Base.metadata` before any fixture
   tries to create the schema, regardless of which test happens to run first.
3. An autouse, function-scoped fixture drops and recreates all tables before
   every single test, so tests never see data left over from another test in
   the same run, and repeated `pytest` invocations are fully deterministic.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(prefix="running_research_test_", suffix=".db")
os.close(_TEST_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "auto"

import app.models  # noqa: E402,F401  (registers all tables on Base.metadata up front)


def pytest_sessionfinish(session, exitstatus):
    try:
        os.remove(_TEST_DB_PATH)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _isolated_schema():
    """Guarantees every test starts from a completely empty database."""
    from app.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    """A FastAPI TestClient wired to the isolated temp database (never the real one)."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    return TestClient(fastapi_app)
