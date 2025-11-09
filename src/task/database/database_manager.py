import sqlite3
import os
import logging


class DatabaseManager:
    """
    A simple wrapper for SQLite database connections and operations.
    - Automatically handles opening and closing the connection.
    - Automatically enables foreign keys (PRAGMA foreign_keys = ON).
    """

    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def create_tables(self, init_sql_file=f"{os.path.dirname(__file__)}/init.sql"):
        """
        create table from init.sql, default init.sql is relative to this file
        """
        self.logger.info(f"Initializing database tables from '{init_sql_file}'...")
        try:
            with open(init_sql_file, "r", encoding="utf-8") as f:
                sql_script = f.read()

            # use entered connection to enable foreign keys and create tables
            with self as conn:
                # DDL
                conn.executescript(sql_script)

            self.logger.info("Database and tables initialized successfully.")
            return True

        except FileNotFoundError:
            self.logger.error(
                f"ERROR: '{init_sql_file}' not found. Tables were not created."
            )
            return False
        except sqlite3.Error as e:
            self.logger.error(f"ERROR during table initialization: {e}")
            return False
