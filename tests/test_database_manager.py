import sqlite3
from task.database.database_manager import DatabaseManager

def test_database_with(tmp_path):
    tmp_db_file = tmp_path / "test_db.db"
    db_manager = DatabaseManager(tmp_db_file)
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
