import sqlite3
import threading
from typing import Optional, List
import logging

from ...utils.config import get_db_path, get_init_sql

class Archive:
    """
    The bedrock of bulletin. Currently implemented as a SQLite database.
    Anybody can read from it. But only one thread may write at a time.
    Only use singleton instance of this class, because it uses a single write lock.
    """

    def __init__(self, db_file: str, init_sql: str):
        self.db_file = db_file
        # Use RLock so the same thread can re-enter write operations when
        # executing inside a `with archive:` context.
        self._write_lock = threading.RLock()
        # thread-local storage for connections used inside a with-context
        self._local = threading.local()
        self._initialize_database(init_sql)
        self.logger = logging.getLogger(__name__)

    def _initialize_database(self, init_sql: str):
        assert init_sql, "Initialization SQL must be provided"
        # initialization should run outside any user transaction
        self.write(init_sql)

    def read(self, sql: str, params: tuple = ()) -> Optional[List[sqlite3.Row]]:
        """
        Create a new connection for each read; connections are not shared between threads.
        Returns list of sqlite3.Row on success, or None on error.
        """
        # make sure is select query
        if not sql.strip().lower().startswith("select"):
            return None
        try:
            conn = sqlite3.connect(self.db_file, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchall()
            return result
        except sqlite3.Error as e:
            self.logger.error(f"Database read error: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _execute(self, sql, params: tuple = ()) -> None:
        """
        Internal method to execute write operation(s) on a fresh connection.
        Supports a single SQL string or an iterable of statements. Each item
        in an iterable may be a string (no params) or a (sql, params) pair.
        Executes all statements in a single transaction; rolls back and raises
        on error.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()

            # multiple statements
            if isinstance(sql, (list, tuple)):
                for item in sql:
                    if isinstance(item, str):
                        cursor.execute(item)
                    else:
                        stmt, stmt_params = item
                        cursor.execute(stmt, stmt_params)
            else:
                cursor.execute(sql, params)

            conn.commit()
        except sqlite3.Error:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.logger.error("Database write error")
            raise
        finally:
            if conn:
                conn.close()

    def write(self, sql, params: tuple = ()):
        """
        Perform the write immediately under a lock. Supports a single SQL
        statement or a list/tuple of statements to be executed in one
        transaction.

        When called inside a `with archive:` context, the write will reuse the
        context's connection and participate in that transaction (no commit is
        performed by write; commit/rollback is handled by the context manager).

        On failure an exception is raised. SELECT statements are rejected.
        """

        # helper to detect select statements
        def _is_select(s: str) -> bool:
            return isinstance(s, str) and s.strip().lower().startswith("select")

        # Normalize and validate: reject any SELECT in write operations
        if isinstance(sql, (list, tuple)):
            for item in sql:
                stmt = item if isinstance(item, str) else item[0]
                if _is_select(stmt):
                    raise ValueError(
                        "SELECT statements are not allowed in write operations"
                    )
        else:
            if _is_select(sql):
                raise ValueError(
                    "SELECT statements are not allowed in write operations"
                )

        # If we are inside a with-context, reuse that connection
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                cursor = conn.cursor()
                if isinstance(sql, (list, tuple)):
                    for item in sql:
                        if isinstance(item, str):
                            cursor.execute(item)
                        else:
                            cursor.execute(item[0], item[1])
                else:
                    cursor.execute(sql, params)
                # do not commit here; commit/rollback is managed by the context
                return
            except sqlite3.Error:
                # propagate the exception so the context manager can rollback
                raise

        # otherwise perform a short transaction with lock and fresh connection
        with self._write_lock:
            success = self._execute(sql, params)
            if not success:
                raise sqlite3.Error("Database write failed")

    def fetch_all(self) -> dict:
        """
        Retrieve all entries from all tables.
        Returns dict of table names to list of dictionaries representing rows.
        """
        # read all tables' entries
        tables = self.read(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        result = {}
        if tables is not None:
            for table in tables:
                rows = self.read(f"SELECT * FROM {table['name']};")
                if rows is not None:
                    result[table["name"]] = [dict(row) for row in rows]
        return result

    def __enter__(self):
        """Begin a transaction context: acquire lock and open a connection for this thread."""
        self._write_lock.acquire()
        conn = sqlite3.connect(self.db_file, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        # start an explicit transaction; IMMEDIATE reduces surprises with locks
        conn.execute("BEGIN IMMEDIATE;")
        self._local.conn = conn
        return conn

    def __exit__(self, exc_type, exc, tb):
        """Commit on success, rollback on exception, close connection and release lock."""
        conn = getattr(self._local, "conn", None)
        try:
            if conn:
                if exc_type is None:
                    conn.commit()
                else:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                conn.close()
        finally:
            if hasattr(self._local, "conn"):
                del self._local.conn
            self._write_lock.release()

_singleton: Optional[Archive] = None

def get_archive() -> Archive:
    global _singleton
    if _singleton is None:
        _singleton = Archive(get_db_path(), get_init_sql())
    return _singleton

def set_archive_for_tests(instance: Optional[Archive]) -> None:
    """在测试中注入或清理单例"""
    global _singleton
    _singleton = instance
