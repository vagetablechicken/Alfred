import pytest

from task import task_engine


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
    return task_engine.task_engine


def test_get_todo_methods(mock_engine):
    engine = mock_engine

    # Create sample todos
    with engine.db as conn:
        cur = conn.cursor()
        # insert todo_templates first
        # run_once default to 0
        cur.executemany(
            """
            INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once, is_active, created_at)
            VALUES (?, ?, ?, ?, 0, 1, ?)
            """,
            [
                (
                    "Alice",
                    "Task A",
                    "* * * * *",
                    "5m",
                    "2025-11-08T09:55:00",
                ),
                (
                    "Bob",
                    "Task B",
                    "* * * * *",
                    "2m",
                    "2025-11-08T09:56:00",
                ),
            ],
        )
        # pretend todo is generated
        cur.executemany(
            """
            INSERT INTO todos (template_id, user_id, reminder_time, ddl_time, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            [
                (
                    1,
                    "Alice",
                    "2025-11-08T10:00:00",
                    "2025-11-08T10:05:00",
                    "2025-11-08T10:00:00",
                    "2025-11-08T10:00:00",
                ),
                (
                    2,
                    "Bob",
                    "2025-11-08T10:01:00",
                    "2025-11-08T10:03:00",
                    "2025-11-08T10:01:00",
                    "2025-11-08T10:01:00",
                ),
            ],
        )

    # Fetch all todos(ordered by reminder_time)
    todos = engine.get_todos()
    assert len(todos) == 2
    user_ids = {todo["user_id"] for todo in todos}
    assert user_ids == {"Alice", "Bob"}

    # Fetch specific todo by id
    todo_id = 2
    todo = engine.get_todo(todo_id)
    assert todo["todo_id"] == todo_id
    assert todo["user_id"] == "Bob"

    # pretend add more todos for next day
    with engine.db as conn:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO todos (template_id, user_id, reminder_time, ddl_time, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            [
                (
                    1,
                    "Alice",
                    "2025-11-09T10:00:00",
                    "2025-11-09T10:05:00",
                    "2025-11-09T10:00:00",
                    "2025-11-09T10:00:00",
                ),
            ],
        )

    # Fetch todos for 2025-11-08
    todos = engine.get_todos("2025-11-08")
    assert len(todos) == 2
    assert todos[0]["user_id"] == "Alice"
    assert todos[1]["user_id"] == "Bob"

    todos = engine.get_todos("2025-11-09")
    assert len(todos) == 1
    assert todos[0]["user_id"] == "Alice"


def test_add_template_and_revoke(mock_engine):
    engine = mock_engine

    # Add a new template
    template_id = engine.add_template(
        user_id="Charlie",
        todo_content="Task C",
        cron="* * * * *",
        ddl_offset="10m",
        run_once=0,
    )
    assert template_id is not None

    # Verify the template is added
    templates = engine.get_templates()
    assert len(templates) == 1
    assert templates[0]["template_id"] == template_id

    engine.run_scheduler(current_time="2025-11-08T11:00:00")

    # Revoke todos by deactivating the template
    engine.set_template_active_status(
        template_id=template_id,
        is_active=False,
        current_time="2025-11-08T11:05:00",
    )

    # Verify that the todos are revoked
    todos = engine.get_todos()
    for todo in todos:
        if todo["template_id"] == template_id:
            assert todo["status"] == "revoked"


def test_todo_escalation(mock_engine):
    engine = mock_engine

    # Add a new template
    template_id = engine.add_template(
        user_id="Dave",
        todo_content="Task D",
        cron="* * * * *",
        ddl_offset="1m",  # short offset for quick escalation
        run_once=0,
    )

    # Run scheduler to create a todo
    engine.run_scheduler(current_time="2025-11-08T12:00:00")
    engine.run_escalator(current_time="2025-11-08T12:00:00")
    # no escalation yet
    todos = engine.get_todos()
    assert len(todos) == 1
    escalated_todos = [todo for todo in todos if todo["status"] == "escalated"]
    assert len(escalated_todos) == 0

    # Advance time to trigger escalation
    engine.run_scheduler(current_time="2025-11-08T12:02:00")
    engine.run_escalator(current_time="2025-11-08T12:02:00")

    # Verify that the todo is escalated
    todos = engine.get_todos()
    assert len(todos) == 2 # one original + one new from scheduler
    escalated_todos = [todo for todo in todos if todo["status"] == "escalated"]
    assert len(escalated_todos) == 1
    assert escalated_todos[0]["template_id"] == template_id
