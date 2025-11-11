"""简单的配置加载器"""

import os
import sys
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _is_pytest_running() -> bool:
    """检测是否在 pytest 环境中运行"""
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
        or any("pytest" in arg.lower() for arg in sys.argv)
    )


def load_config(config_file: str = None):
    """
    加载配置文件

    优先级:
    1. config_file 参数
    2. ALFRED_CONFIG 环境变量
    3. pytest 环境下自动使用 config.test.yaml
    4. 默认使用 config.yaml
    """
    if config_file is None:
        # 检查环境变量
        config_file = os.getenv("ALFRED_CONFIG")

        if config_file is None:
            # pytest 运行时自动使用测试配置
            if _is_pytest_running():
                config_file = "config.test.yaml"
            else:
                config_file = "config.yaml"
            logger.info(f"No config file specified, using default: {config_file}")
        else:
            logger.info(f"Using config file from ALFRED_CONFIG: {config_file}")

    # 找到项目根目录
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / config_file

    if not config_path.exists():
        logger.warning(f"Config file {config_path} does not exist. Using empty config.")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_vault_path(config_file: str = None) -> str:
    config = load_config(config_file)
    db_path = config.get("vault", {}).get("path", "")
    if not db_path:
        raise ValueError("Vault database path not configured.")
    # 如果是相对路径且不是内存数据库，转为绝对路径
    if not os.path.isabs(db_path) and db_path != ":memory:":
        project_root = Path(__file__).parent.parent.parent
        db_path = str(project_root / db_path)

    return db_path


def get_init_sql(config_file: str = None) -> str:
    config = load_config(config_file)
    # use default init sql if not specified, relative to root
    init_sql = config.get("vault", {}).get("init_sql", "src/task/vault/sqlite_init.sql")

    # 如果是相对路径，转为绝对路径
    if not os.path.isabs(init_sql):
        project_root = Path(__file__).parent.parent.parent
        init_sql = str(project_root / init_sql)

    # read yaml file content
    with open(init_sql, "r", encoding="utf-8") as f:
        return f.read()


def get_slack_channel(config_file: str = None) -> str:
    """read file every time to get update"""
    config = load_config(config_file)
    # can't be None here, must be set in config
    channel = config.get("slack").get("channel")
    return channel


def setup_global_logger(
    console_level=logging.INFO, file_level=logging.DEBUG, log_file_name="app.log"
):
    """
    配置一个简单、可重用的全局日志记录器。

    它会同时将日志输出到：
    1. 控制台 (StreamHandler)
    2. 日志文件 (FileHandler)

    参数:
    console_level (int): 控制台输出的最低日志级别 (默认: INFO)
    file_level (int): 文件输出的最低日志级别 (默认: DEBUG)
    log_file_name (str): 日志文件的名称 (默认: app.log)
    """

    # 1. 获取根记录器 (root logger)
    # 根记录器是所有 logging.getLogger(__name__) 的父级
    logger = logging.getLogger()

    # 设置根记录器的最低处理级别为 DEBUG，
    # 这样它才能处理所有级别的日志，具体的过滤交给 Handlers
    logger.setLevel(logging.DEBUG)

    # 2. 清除所有已存在的 Handlers（防止重复配置）
    # 在简单脚本中这很方便。
    # 如果您在更复杂的环境（如库）中使用，请小心。
    if logger.hasHandlers():
        logger.handlers.clear()

    # 3. 创建一个通用的日志格式
    # [时间] - [级别] - [模块名] - (文件名:行号) - [消息]
    formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s"
    )

    # 4. 创建并配置控制台 Handler (StreamHandler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 5. 创建并配置文件 Handler (FileHandler)
    try:
        # 使用 'a' 模式（追加）和 'utf-8' 编码
        file_handler = logging.FileHandler(log_file_name, mode="a", encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError as e:
        logger.error(f"无法创建日志文件 {log_file_name}. 错误: {e}")
        # 即使文件创建失败，控制台日志依然可以工作

    logger.info("日志系统配置完成。")
    logger.info(
        f"控制台级别: {logging.getLevelName(console_level)}, 文件级别: {logging.getLevelName(file_level)}"
    )
