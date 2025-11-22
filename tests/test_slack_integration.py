from datetime import datetime, time, timedelta
import pytest
from unittest.mock import Mock
from alfred.slack.patrol_launcher import patrol_job
from alfred.slack.butler import butler


@pytest.mark.integration
def test_butler_send_slack_with_bulletin_todos(monkeypatch):
    """Test Butler gets TODOs through Bulletin and sends Slack messages"""
    # Mock Bulletin
    mock_bulletin = Mock()
    current_time = datetime.now()
    mock_todos = [
        {
            "remind_time": (current_time - timedelta(hours=1)).isoformat(),
            "ddl_time": (current_time + timedelta(seconds=1)).isoformat(),
            "todo_id": 1,
            "status": "pending",
            "user_id": 123,
            "content": "Complete the report",
        },
        {
            "remind_time": (current_time - timedelta(hours=1)).isoformat(),
            "ddl_time": (current_time + timedelta(seconds=1)).isoformat(),
            "todo_id": 2,
            "status": "finished",
            "user_id": 123,
            "content": "Attend the meeting",
        },
        {
            "remind_time": (current_time - timedelta(hours=2)).isoformat(),
            "ddl_time": (current_time - timedelta(hours=1)).isoformat(),
            "todo_id": 3,
            "status": "pending",
            "user_id": 123,
            "content": "Submit the assignment",
        },
        {
            "remind_time": (current_time + timedelta(hours=1)).isoformat(),
            "ddl_time": (current_time + timedelta(hours=2)).isoformat(),
            "todo_id": 4,
            "status": "pending",
            "user_id": 123,
            "content": "Prepare for the presentation",
        },
    ]
    mock_bulletin.get_todos.return_value = mock_todos

    # use mocked bulletin in Butler instance
    monkeypatch.setattr(butler, "bulletin", mock_bulletin)
    # Set summary_time to midnight so it always triggers during the test
    monkeypatch.setattr(butler, "summary_time", time(hour=0, minute=0))

    # Run once
    patrol_job()
