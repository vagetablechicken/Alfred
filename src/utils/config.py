import logging
import sys

...


def get_db_path() -> str:
    # Return the database file path
    return "path/to/your/database.db"


def get_init_sql() -> str:
    # read the initialization SQL from a file or define it here
    sql_path = "path/to/your/init.sql"
    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            return f.read()
    except IOError as e:
        logging.error(f"Can't read init SQL file {sql_path}: {e}")
        return ""


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
