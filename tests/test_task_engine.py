import datetime
import pytest

from task import task_engine
from task.database.database_manager import DatabaseManager


class DummyCron:
    def __init__(self, sim_time):
        # store the simulation time passed to croniter stub
        self.sim_time = sim_time

    def get_prev(self, _):
        # return the previous minute (ceiling to minute start)
        return self.sim_time.replace(second=0, microsecond=0)


@pytest.fixture
def mock_engine(tmp_path, monkeypatch):
    # use origin init.sql but db file in tmp_path
    tmp_db_file = tmp_path / "test_tasks.db"
    database_manager = DatabaseManager(tmp_db_file)
    database_manager.create_tables()

    # monkeypatch the imported 'croniter' in task engine to use DummyCron
    def croniter_stub(cron_expr, sim_time):
        return DummyCron(sim_time)

    te = task_engine.TaskEngine(database_manager)
    monkeypatch.setattr(task_engine, "croniter", croniter_stub)
    return te


def _fetchall(conn, query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def test_scheduler_idempotency_and_basic_flow(mock_engine):
    engine = mock_engine

    # Add two templates: Alice (5m ddl) and Bob (2m ddl)
    alice_template = engine.add_template("Alice", "每分钟打卡", "* * * * *", "5m")
    bob_template = engine.add_template("Bob", "每分钟喝水", "* * * * *", "2m")

    # T=1: run scheduler at 10:00:05 -> should create tasks at 10:00:00
    sim_t1 = datetime.datetime(2025, 11, 8, 10, 0, 5)
    engine.run_scheduler(sim_t1)

    with engine.db as conn:
        rows = _fetchall(
            conn,
            "SELECT user_id, reminder_time, ddl_time, status FROM todos ORDER BY id",
        )
        assert len(rows) == 2
        # ensure both users have 10:00:00 reminder_time
        reminders = {r[0]: r[1] for r in rows}
        assert reminders["Alice"].startswith("2025-11-08T10:00:00")
        assert reminders["Bob"].startswith("2025-11-08T10:00:00")

    # T=2: run scheduler again at same simulation time -> idempotency, no new tasks
    engine.run_scheduler(sim_t1)
    with engine.db as conn:
        rows = _fetchall(conn, "SELECT COUNT(*) FROM todos")
        assert rows[0][0] == 2

    # T=3: run scheduler at 10:01:05 -> should create another pair at 10:01:00
    sim_t2 = datetime.datetime(2025, 11, 8, 10, 1, 5)
    engine.run_scheduler(sim_t2)
    with engine.db as conn:
        rows = _fetchall(
            conn, "SELECT id, user_id, reminder_time FROM todos ORDER BY id"
        )
        # now 4 todos total
        assert len(rows) == 4
        # find Alice's 10:01 task id for later use
        alice_100 = [
            r
            for r in rows
            if r[1] == "Alice" and r[2].startswith("2025-11-08T10:00:00")
        ]
        alice_101 = [
            r
            for r in rows
            if r[1] == "Alice" and r[2].startswith("2025-11-08T10:01:00")
        ]
        assert alice_100 and alice_101

    # T=4: complete Alice's 10:00 task
    alice_100_id = alice_100[0][0]
    sim_complete = datetime.datetime(2025, 11, 8, 10, 1, 10)
    engine.complete_task(todo_id=alice_100_id, sim_time=sim_complete)
    with engine.db as conn:
        status = _fetchall(
            conn, "SELECT status FROM todos WHERE id = ?", (alice_100_id,)
        )[0][0]
        assert status == "completed"

    # T=5: escalation at 10:03:00 should escalate Bob's 10:00 task (ddl 10:02)
    sim_escalate = datetime.datetime(2025, 11, 8, 10, 3, 0)
    engine.run_escalation(sim_escalate)
    with engine.db as conn:
        bob_100 = _fetchall(
            conn,
            "SELECT id, status FROM todos WHERE user_id = ? AND reminder_time LIKE ?",
            ("Bob", "2025-11-08T10:00:%"),
        )[0]
        assert bob_100[1] == "escalated"

    # T=6: revert completion for Alice's 10:01 task (simulate wrong click)
    alice_101_id = alice_101[0][0]
    # First complete it
    engine.complete_task(
        todo_id=alice_101_id, sim_time=datetime.datetime(2025, 11, 8, 10, 2, 0)
    )
    # Then revert at 10:03:10 (DDL for Alice@10:01 is 10:06 -> should revert to 'pending')
    engine.revert_task_completion(
        todo_id=alice_101_id, sim_time=datetime.datetime(2025, 11, 8, 10, 3, 10)
    )
    with engine.db as conn:
        status = _fetchall(
            conn, "SELECT status FROM todos WHERE id = ?", (alice_101_id,)
        )[0][0]
        assert status == "pending"

    # T=7: disable Bob's template -> should mark Bob's pending/escalated todos as revoked
    sim_admin = datetime.datetime(2025, 11, 8, 10, 3, 30)
    engine.set_template_active_status(
        template_id=bob_template, is_active=False, sim_time=sim_admin
    )
    with engine.db as conn:
        bob_rows = _fetchall(
            conn, "SELECT status FROM todos WHERE user_id = ?", ("Bob",)
        )
        assert all(r[0] == "revoked" for r in bob_rows)

    # T=8: run scheduler at 10:04:05 -> should only create Alice's 10:04 task (Bob inactive)
    sim_t3 = datetime.datetime(2025, 11, 8, 10, 4, 5)
    engine.run_scheduler(sim_t3)
    with engine.db as conn:
        # count Alice tasks (should have at least 3 now), Bob should not have a new task at 10:04
        bob_100plus = _fetchall(
            conn,
            "SELECT COUNT(*) FROM todos WHERE user_id = ? AND reminder_time LIKE ?",
            ("Bob", "2025-11-08T10:04:%"),
        )[0][0]
        assert bob_100plus == 0
