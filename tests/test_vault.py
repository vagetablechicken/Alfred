import threading
import sqlite3


def test_write_and_read_basic(mock_vault):
    # simple write
    with mock_vault.transaction() as cur:
        cur.execute(
            "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
            (1, "t1", "* * * * *", "5m", 0),
        )
    with mock_vault.transaction() as cur:
        rows = cur.execute("SELECT * FROM todo_templates").fetchall()
    assert rows and len(rows) == 1


def test_context_transaction_commit(mock_vault):
    with mock_vault.transaction() as cur:
        cur.execute(
            "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
            (2, "t2", "* * * * *", "5m", 0),
        )
        cur.execute(
            "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
            (3, "t3", "* * * * *", "5m", 0),
        )
    with mock_vault.transaction() as cur:
        rows = cur.execute(
            "SELECT * FROM todo_templates ORDER BY template_id"
        ).fetchall()
    assert rows and len(rows) == 2


def test_context_transaction_rollback_on_error(mock_vault):
    try:
        with mock_vault.transaction() as cur:
            cur.execute(
                "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
                (4, "t4", "* * * * *", "5m", 0),
            )
            # cause an error: table does not exist
            cur.execute("INSERT INTO unknown_table (a) VALUES (?)", (1,))
    except sqlite3.Error:
        pass

    with mock_vault.transaction() as cur:
        rows = cur.execute(
            "SELECT * FROM todo_templates ORDER BY template_id"
        ).fetchall()
    # transaction should have been rolled back
    assert not rows


def test_concurrent_writes(mock_vault):
    def worker(i):
        for j in range(10):
            with mock_vault.transaction() as cur:
                cur.execute(
                    "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
                    (i, f"t{i}-{j}", "* * * * *", "5m", 0),
                )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with mock_vault.transaction() as cur:
        rows = cur.execute("SELECT * FROM todo_templates").fetchall()
    assert rows and len(rows) == 4 * 10


def test_fetch_all(mock_vault):
    # insert sample data
    with mock_vault.transaction() as cur:
        cur.execute(
            "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
            (1, "t1", "* * * * *", "5m", 0),
        )
        cur.execute(
            "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
            (2, "t2", "* * * * *", "10m", 1),
        )

    with mock_vault.transaction() as cur:
        cur.execute("SELECT * FROM todo_templates")
        all_data = cur.fetchall()
    assert all_data and len(all_data) == 2
