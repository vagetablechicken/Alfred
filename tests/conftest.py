"""pytest configuration and fixtures"""

import sys
import os
from unittest.mock import MagicMock
import pytest

from alfred.task.vault import LockedSqliteVault

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
sys.modules['slack_bolt'] = mock_slack_bolt
sys.modules['slack_bolt.adapter'] = MagicMock()
sys.modules['slack_bolt.adapter.socket_mode'] = MagicMock()




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

    yield vault
