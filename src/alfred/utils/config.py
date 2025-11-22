"""Simple configuration loader"""

import os
import sys
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _is_pytest_running() -> bool:
    """Detect if running in pytest environment"""
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
        or any("pytest" in arg.lower() for arg in sys.argv)
    )


def load_config(config_file: str = None):
    """
    Load configuration file

    Priority:
    1. config_file parameter
    2. ALFRED_CONFIG environment variable
    3. Auto use config.test.yaml in pytest environment
    4. Default to config.yaml
    """
    if config_file is None:
        # Check environment variable
        config_file = os.getenv("ALFRED_CONFIG")

        if config_file is None:
            # Auto use test config when running pytest
            if _is_pytest_running():
                config_file = "config.test.yaml"
            else:
                config_file = "config.yaml"
            logger.info(f"No config file specified, using default: {config_file}")
        else:
            logger.info(f"Using config file from ALFRED_CONFIG: {config_file}")

    # if relative path, based on current running dir
    config_path = Path(config_file)
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
    # validate path, only support sqlite and postgresql for now
    if not (db_path.startswith("sqlite://") or db_path.startswith("postgresql://")):
        raise ValueError("Unsupported vault database path. Only sqlite and postgresql are supported.")

    return db_path

def get_slack_channel(config_file: str = None) -> str:
    """Read file every time to get update"""
    config = load_config(config_file)
    # can't be None here, must be set in config
    channel = config.get("slack").get("channel")
    return channel


def get_slack_admin(config_file: str = None) -> str:
    """Read file every time to get update"""
    config = load_config(config_file)
    # can't be None here, must be set in config
    admin = config.get("slack").get("admin")
    assert isinstance(admin, list), "Slack admin config must be a list of user IDs"
    return admin


def setup_global_logger(
    console_level="INFO", file_level="DEBUG", log_file_name="alfred.log"
):
    """
    Set up a global logger with both console and file handlers.
    """

    # 1. Get root logger
    logger = logging.getLogger()

    # Set root logger's minimum level to DEBUG,
    # so it can handle all log levels, specific filtering is delegated to Handlers
    logger.setLevel(logging.DEBUG)

    # [Time] - [Level] - [Module] - (File:Line) - [Message]
    formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s"
    )

    # Create and configure console Handler (StreamHandler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create and configure file Handler (FileHandler)
    try:
        # Use 'a' mode (append) with 'utf-8' encoding
        file_handler = logging.FileHandler(log_file_name, mode="a", encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError as e:
        logger.error(f"Unable to create log file {log_file_name}. Error: {e}")
        # Console logging still works even if file creation fails

    logger.info("Logging system configured.")
    logger.info(
        f"Console level: {logging.getLevelName(console_level)}, File level: {logging.getLevelName(file_level)}"
    )
