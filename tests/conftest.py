"""pytest configuration and fixtures"""

from pathlib import Path

import pytest

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
