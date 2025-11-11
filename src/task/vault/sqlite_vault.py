from contextlib import contextmanager
import sqlite3
import threading
import logging

from utils.config import get_vault_path, get_init_sql

logger = logging.getLogger(__name__)

class LockedSqliteVault:
    """
    一个线程安全的单例 SQLite 包装器。

    它使用 Python 的 threading.Lock 来序列化来自不同线程的“事务”，
    并使用 WAL 模式和 timeout 来优化数据库层面的并发。
    """

    _instance = None
    _lock = threading.Lock()  # 1. 这是一个 Python 线程锁

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.db_path = get_vault_path()
        logger.info(f"[Vault] 正在初始化: {self.db_path}")

        # 2. (关键) 允许多个线程使用此连接
        #    timeout=10 意味着如果DB被锁，它会等待10秒
        self.conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)

        # 3. (关键) 启用 WAL 模式，极大提升并发性
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            logger.info("[Vault] WAL 模式已启用。")
        except Exception as e:
            logger.info(f"[Vault] 警告：启用 WAL 失败: {e}")

        # init sql
        init_sql = get_init_sql()
        with self.conn:
            self.conn.executescript(init_sql)
            logger.info("[Vault] 数据库架构已初始化。")

        # use Row
        self.conn.row_factory = sqlite3.Row

        # 4. (关键) 创建我们自己的锁，用于事务
        self._transaction_lock = threading.Lock()

        self._initialized = True
        logger.info("[Vault] 初始化完成。")

    @contextmanager
    def transaction(self):
        """
        这就是你想要的“带锁的 with 语句”。
        它保证在同一时间，只有一个线程可以执行 "with" 块内的代码。
        """
        thread_id = threading.current_thread().name
        logger.info(f"[{thread_id}] 正在等待获取事务锁...")

        # 步骤 1: 获取 Python 线程锁
        # (如果另一个线程在 'with' 块中，这里会阻塞)
        self._transaction_lock.acquire()
        logger.info(f"[{thread_id}] 事务锁已获取。")

        cursor = self.conn.cursor()
        try:
            # 步骤 2: 开始数据库事务 (隐式)
            # 'yield' 关键字把 cursor 交给 'with' 语句
            yield cursor

            # 步骤 3: 如果 'with' 块成功，提交数据库事务
            logger.info(f"[{thread_id}] 正在提交数据库...")
            self.conn.commit()

        except Exception as e:
            # 步骤 4: 如果 'with' 块失败，回滚数据库事务
            logger.info(f"[{thread_id}] 事务失败，正在回滚... 错误: {e}")
            self.conn.rollback()
            raise  # 重新抛出异常，让调用者知道

        finally:
            # 步骤 5: 释放 Python 线程锁
            # (允许下一个等待的线程进入)
            cursor.close()
            logger.info(f"[{thread_id}] 事务锁已释放。")
            self._transaction_lock.release()
