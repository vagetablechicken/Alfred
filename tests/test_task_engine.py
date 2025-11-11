import pytest

from task import vault, task_engine
from task.bulletin import Bulletin


class DummyCron:
    def __init__(self, sim_time):
        # store the simulation time passed to croniter stub
        self.sim_time = sim_time

    def get_prev(self, _):
        # return the previous minute (ceiling to minute start)
        return self.sim_time.replace(second=0, microsecond=0)


@pytest.fixture
def mock_engine(monkeypatch):
    # monkeypatch the imported 'croniter' in task engine to use DummyCron
    def croniter_stub(cron_expr, current_time):
        return DummyCron(current_time)

    monkeypatch.setattr(task_engine, "croniter", croniter_stub)
    return task_engine.instance


def test_add_template_and_revoke(mock_engine):
    engine = mock_engine
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

    engine.run_scheduler(current_time="2025-11-08T11:00:00")

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
