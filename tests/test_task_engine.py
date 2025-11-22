import pytest

from alfred.task import task_engine
from alfred.task.bulletin import Bulletin


class DummyCron:
    def __init__(self, sim_time):
        # store the simulation time passed to croniter stub
        self.sim_time = sim_time

    def get_prev(self, _):
        # return the previous minute (ceiling to minute start)
        return self.sim_time.replace(second=0, microsecond=0)


@pytest.fixture
def mock_croniter(monkeypatch):
    # monkeypatch croniter in bulletin module
    def croniter_stub(cron_expr, current_time):
        return DummyCron(current_time)

    from alfred.task import bulletin
    monkeypatch.setattr(bulletin, "croniter", croniter_stub)
    return croniter_stub


def test_add_template_and_revoke(mock_croniter):
    bulletin = Bulletin()
    # Add a new template
    template_id = bulletin.add_template(
        user_id="Charlie",
        todo_content="Task C",
        cron="* * * * *",
        ddl_offset="10m",
        run_once=0,
    )
    assert template_id is not None

    # Verify the template is added
    templates = bulletin.get_templates()
    assert len(templates) == 1
    assert templates[0]["template_id"] == template_id

    task_engine.run_scheduler(current_time="2025-11-08T11:00:00")

    # Revoke todos by deactivating the template
    bulletin.set_template_active_status(
        template_id=template_id,
        is_active=False,
        current_time="2025-11-08T11:05:00",
    )

    # Verify that the todos are revoked
    todos = bulletin.get_todos()
    for todo in todos:
        if todo["template_id"] == template_id:
            assert todo["status"] == "revoked"
