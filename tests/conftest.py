"""pytest configuration and fixtures"""

import sys
import os
from pathlib import Path

import pytest

# Ensure the project's source directory is on sys.path so tests can import
# modules as they expect (e.g. `from task.bulletin import Bulletin`).
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "alfred"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from task.vault import LockedSqliteVault


@pytest.fixture(autouse=True)
def mock_vault():
    """
    Fixture to provide a clean vault for each test.
    """
    vault = LockedSqliteVault()
    with vault.transaction() as cur:
        cur.execute("DELETE FROM todos")
        cur.execute("DELETE FROM todo_templates")
        cur.execute("DELETE FROM todo_status_logs")

    yield
