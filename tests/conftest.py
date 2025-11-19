"""pytest configuration and fixtures"""

import sys
import os
from unittest.mock import MagicMock
import pytest


def pytest_configure(config):
    """Configure pytest and setup mocks based on marker expression"""
    # Mock Slack for unit tests before any imports happen
    # Check if we're running integration tests by looking at the -m marker expression
    markexpr = config.getoption("-m", default="")

    # Only mock if NOT explicitly running integration tests
    # Skip mocking if user explicitly runs: -m integration
    should_mock = markexpr != "integration"

    if should_mock:
        _setup_slack_mocks()


def _setup_slack_mocks():
    """Set up Slack mocks for unit tests"""

    # Set required Slack environment variables for testing
    # These must be set before importing any alfred modules
    os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
    os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-token")

    # Create a mock App class that doesn't validate tokens
    class MockApp:
        def __init__(self, *args, **kwargs):
            self.client = MagicMock()
            self.client.chat_postMessage = MagicMock(return_value={"ok": True})

    mock_slack_bolt = MagicMock()
    mock_slack_bolt.App = MockApp
    sys.modules["slack_bolt"] = mock_slack_bolt
    sys.modules["slack_bolt.adapter"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode"] = MagicMock()


@pytest.fixture(autouse=True)
def mock_vault():
    """
    Fixture to provide a clean vault for each test.
    """
    from alfred.task.vault import LockedSqliteVault

    vault = LockedSqliteVault()
    with vault.transaction() as cur:
        cur.execute("DELETE FROM todos")
        cur.execute("DELETE FROM todo_templates")
        cur.execute("DELETE FROM todo_status_logs")

    yield vault
