import sqlite3
import threading
import time

from task.database.database_manager import DBSession

def test_database_with():
    db_manager = DBSession()
    with db_manager as conn:
        assert conn is not None
        assert conn.total_changes == 0
        cur = conn.cursor()
        assert cur is not None

        # Create a test table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        assert cur.lastrowid is not None

        # Insert a test user
        cur.execute("""
            INSERT INTO users (name) VALUES ('Alice')
        """)
        assert cur.lastrowid is not None

        # Query the test user
        cur.execute("""
            SELECT * FROM users
        """)
        result = cur.fetchall()
        assert result is not None
        assert len(result) == 1
        assert result[0][1] == 'Alice'

        assert conn.total_changes == 1  # one for insert

    # conn is closed after exiting the with block
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError as e:
        assert "closed" in str(e)

    # a new conn
    with db_manager as conn2:
        assert conn2 is not None
        assert conn2 != conn  # different connection objects
        assert conn2.total_changes == 0  # no changes yet

def test_multithreaded_dbsession(tmp_path):
    db_file = tmp_path / "thread_test.db"
    # 初始化表结构
    db = DBSession(db_file)
    with open(f"{db.__class__.__module__.replace('.', '/')}/init.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    with db as conn:
        conn.executescript(sql_script)

    def worker(thread_id):
        session = DBSession(db_file)
        with session as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (name) VALUES (?)", (f"user_{thread_id}",))
            time.sleep(0.1)  # 模拟操作耗时

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 检查所有数据是否插入成功
    with db as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM users ORDER BY name")
        names = [row[0] for row in cur.fetchall()]
    assert names == [f"user_{i}" for i in range(5)]
