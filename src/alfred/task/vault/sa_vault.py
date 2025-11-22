from contextlib import contextmanager
import logging
from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

from alfred.utils.config import get_vault_path
from alfred.task.vault.models import Base


class Vault:
    """
    SQLAlchemy wrapper.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_url = get_vault_path()
        self.logger.info(f"[Vault] Initializing SQLAlchemy: {self.db_url}")

        self.engine = self._create_engine(self.db_url)
        self.Session = scoped_session(sessionmaker(bind=self.engine))

        self._init_schema()
        self.logger.info("[Vault] Initialization complete.")

    def _create_engine(self, url: str):
        if url.startswith("sqlite"):
            engine = create_engine(
                url,
                connect_args={"check_same_thread": False, "timeout": 30},
                pool_pre_ping=True,
            )

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

            return engine

        return create_engine(
            url, pool_size=20, max_overflow=10, pool_timeout=30, pool_pre_ping=True
        )

    def _init_schema(self):
        try:
            Base.metadata.create_all(self.engine)
        except Exception as e:
            self.logger.error(f"[Vault] Schema initialization failed: {e}")
            raise

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @property
    def db(self):
        """Shorthand for session_scope - use with context manager: with vault.db as s:"""
        return self.session_scope()


@lru_cache
def get_vault():
    """Singleton accessor for Vault"""
    return Vault()
