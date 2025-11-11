import threading
import sqlite3

import pytest

from task.database.archive import Archive, get_archive, set_archive_for_tests

@pytest.fixture(autouse=True)
def mock_archive_init(temp_path):
    INIT_SQL = """
    CREATE TABLE IF NOT EXISTS todo_templates (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        todo_content TEXT NOT NULL
    );
    """
    archive = Archive(str(temp_path / "test.db"), init_sql=INIT_SQL)
    set_archive_for_tests(archive)
    yield
    set_archive_for_tests(None)

def test_write_and_read_basic():
    arch = get_archive()
    # simple write
    ok = arch.write("INSERT INTO todo_templates (user_id, todo_content) VALUES (?, ?)", (1, 't1'))
    assert ok

    rows = arch.read("SELECT * FROM todo_templates")
    assert rows and len(rows) == 1


def test_context_transaction_commit():
    arch = get_archive()

    with arch:
        arch.write("INSERT INTO todo_templates (user_id, todo_content) VALUES (?, ?)", (2, 't2'))
        arch.write("INSERT INTO todo_templates (user_id, todo_content) VALUES (?, ?)", (3, 't3'))

    rows = arch.read("SELECT * FROM todo_templates ORDER BY template_id")
    assert rows and len(rows) == 2


def test_context_transaction_rollback_on_error():
    arch = get_archive()

    try:
        with arch:
            arch.write("INSERT INTO todo_templates (user_id, todo_content) VALUES (?, ?)", (4, 't4'))
            # cause an error: table does not exist
            arch.write("INSERT INTO unknown_table (a) VALUES (?)", (1,))
    except sqlite3.Error:
        pass

    rows = arch.read("SELECT * FROM todo_templates ORDER BY template_id")
    # transaction should have been rolled back
    assert not rows


def test_concurrent_writes():
    arch = get_archive()

    def worker(i):
        for j in range(10):
            arch.write("INSERT INTO todo_templates (user_id, todo_content) VALUES (?, ?)", (i, f't{i}-{j}'))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = arch.read("SELECT * FROM todo_templates")
    assert rows and len(rows) == 4 * 10
