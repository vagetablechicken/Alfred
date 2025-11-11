"""pytest configuration and fixtures"""
import os
import pytest
from pathlib import Path
from task.task_engine import TaskEngine
from utils.config import get_db_path


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """在测试会话开始前和结束后清理测试数据库"""
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    test_db = project_root / "test_tasks.db"
    
    # 测试开始前：删除旧的测试数据库
    if test_db.exists():
        os.remove(test_db)
        print(f"\n已删除旧的测试数据库: {test_db}")
    
    yield  # 运行所有测试
    
    # 测试结束后：可选择保留或删除测试数据库用于调试
    # 如果想保留测试数据库用于调试，注释掉下面的代码
    if test_db.exists():
        os.remove(test_db)
        print(f"\n已删除测试数据库: {test_db}")


@pytest.fixture(scope="function")
def task_engine():
    """每次测试自动创建新的 TaskEngine 实例，使用测试数据库"""
    db_file = get_db_path("config.test.yaml")
    engine = TaskEngine(db_file=db_file)
    # 可选：初始化表结构
    with engine._get_db() as conn:
        with open(f"src/task/database/init.sql", "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)
    return engine
