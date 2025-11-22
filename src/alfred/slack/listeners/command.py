import enum
from croniter import croniter
import re
import typer
import shlex

from alfred.slack.block_builder import BlockBuilder
from alfred.utils.config import get_slack_admin
from alfred.utils.format import format_templates, format_todo_logs, format_todos

from ..app import app
from ..butler import butler


@app.command("/alfred")
def handle_alfred_command(ack, body, client, logger, say):
    """
    Handle /alfred command
    'say' is ephemeral by default in commands
    """
    # Immediately ACK (within 3 seconds)
    ack()

    user_id = body["user_id"]
    # text is no /alfred prefix
    text = body.get("text", "").strip()
    logger.info(f"User {user_id} triggered /alfred with: {text}")

    if (admin_list := get_slack_admin()) and (user_id not in admin_list):
        say("❌ *Permission Denied*: You are not an admin.")
        logger.warning(f"User {user_id} is not an admin. Permission denied.")
        return

    try:
        args_list = shlex.split(text)
        logger.debug(f"Parsed args: {args_list}")
        alfred_cli_app(args_list, obj=AppState(logger, say))
    except typer.BadParameter as e:
        # Typer 的验证错误
        logger.exception(f"Typer parameter error: {e}")
        say(f"❌ *参数错误*:\n`{e}`")
    except SystemExit as e:
        # Typer 默认在 --help 或出错时会退出程序
        if e.code == 0:
            logger.info("\n--- Typer 帮助信息 (已捕获) ---")
            # normal exit
        else:
            logger.info("\n--- Typer 参数错误 (已捕获) ---")
            logger.info("  (Tip: 可能是缺少了必需的参数)")
            say(f"❌ *参数错误*:\n`请检查您的命令格式或使用 /alfred help 获取帮助`")
    except Exception as e:
        logger.exception(f"Unknown error: {e}")
        say(f"❌ *发生错误*:\n`{e}`")


# bind logger and say to AppState for Typer commands
class AppState:
    def __init__(self, logger, say):
        self.logger = logger
        self.say = say


# validators for Typer arguments
def validate_cron(value: str) -> str:
    """检查是否为有效的 Cron 表达式"""
    if not croniter.is_valid(value):
        raise typer.BadParameter(f"'{value}' 不是一个有效的 cron 表达式")
    # print(f"Validated Cron: {value}")
    return value


def validate_duration(value: str) -> str:
    """
    验证 offset 字段.
    解析 '1h', '3m', '5m', '1d' 或 '1' (代表 1d).
    """
    value_str = str(value).strip().lower()

    match = re.match(r"^(\d+)([smhd])$", value_str)
    if match:
        # 验证通过 (e.g., '1h', '3m')
        # print(f"Validated Duration: {value_str}")
        return value_str

    match_int = re.match(r"^(\d+)$", value_str)
    if match_int:
        # 验证通过 (e.g., '1', 假定为 '1d')
        # print(f"Validated Duration: {value_str} (assumed days)")
        return value_str

    raise typer.BadParameter(f"无法解析的持续时间/bias格式: '{value}'")


class ListCategory(str, enum.Enum):
    todos = "todos"
    templates = "templates"


def help_string():
    return (
        "*Alfred Bot Command Help:*\n"
        "• `/alfred add template <user_id> <name> <cron> <offset> [<run_once>]`\n"
        "  run_once is optional, 1 = run once then disable, 0 = run periodically, default is 0\n"
        "  (Example: `/alfred add template 'U0xxx' 'Review' '0 9 * * 1-5' '1h' '1'`)\n"
        "• `/alfred list [todos|templates]`\n"
        "  (Default is `todos`)\n"
        "• `/alfred log <todo_id>`\n"
        "  (Show log for a specific todo ID)\n"
        "• `/alfred test`\n"
        "  (Send a test Block Kit message)\n"
        "• `/alfred help`\n"
        "  (Show this help information)\n"
    )


alfred_cli_app = typer.Typer(
    help=help_string(),
    add_completion=False,  # slack bot can't use shell completion
)


add_app = typer.Typer(help="添加一个新任务模板 (e.g., 'template')")
alfred_cli_app.add_typer(add_app, name="add")


@add_app.command(
    "template",
    help="• /alfred add template <user_id> <name> <cron> <offset> [<run_once>]",
)
def add_template(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="用户的 ID (e.g., 'U0xxx')"),
    name: str = typer.Argument(..., help="模板的名称 (e.g., 'Review')"),
    cron: str = typer.Argument(..., callback=validate_cron, help="Cron 格式的时间表"),
    offset: str = typer.Argument(
        ..., callback=validate_duration, help="提醒间隔/偏移 (e.g., '1h')"
    ),
    # optional argument with default
    run_once: int = typer.Argument(0, help="1 = 运行一次, 0 = 周期运行 (默认: 0)"),
):
    """
    添加一个任务模板。
    """
    template_id = butler.add_template(user_id, name, cron, offset, run_once)
    ctx.obj.logger.info(
        f"User <@{user_id}> added template {template_id} for <@{user_id}>"
    )
    ctx.obj.say(f"Added template ID {template_id} for <@{user_id}>.")


# --- 3.2. 'list' 命令 ---
@alfred_cli_app.command(
    "list", help="• /alfred list [todos|templates] (Default is 'todos')"
)
def list_items(
    ctx: typer.Context,
    category: ListCategory = typer.Argument(
        ListCategory.todos,
        case_sensitive=False,
        help="要列出的项目类型 (todos 或 templates)",
    ),
):
    """
    列出 todos 或 templates.
    """
    logger = ctx.obj.logger
    say = ctx.obj.say
    logger.info(f"Category: {category.value}")  # 'todos' 或 'templates'

    if category == ListCategory.todos:
        logger.info("正在获取所有 active todos...")
        # admin may want to see all todos
        todos = butler.get_todos()
        todo_list = format_todos(todos)
        logger.debug(f"Listing todos: {todo_list}")
        say(f"*TODOs:*\n{todo_list}")
    elif category == ListCategory.templates:
        logger.info("正在获取所有 templates...")
        templates = butler.get_templates()
        template_list = format_templates(templates)
        logger.debug(f"Listing templates: {template_list}")
        say(f"*Task Templates:*\n{template_list}")


# --- 3.3. 'log' 命令 ---
@alfred_cli_app.command(
    "log", help="• /alfred log <todo_id> (Show log for a specific todo ID)"
)
def log_todo(
    ctx: typer.Context,
    todo_id: str = typer.Argument(..., help="要查看日志的 TODO ID"),
):
    """
    标记一个 todo 为 'completed'.
    """
    logger = ctx.obj.logger
    say = ctx.obj.say
    logger.info(f"Getting log for todo_id: {todo_id}")

    todo_log = butler.get_todo_log(todo_id)
    log_string = format_todo_logs(todo_log)
    logger.debug(f"Fetched log for todo_id {todo_id}:\n{log_string}")
    say(f"""TODO log for ID {todo_id}:\n{log_string}""")


@alfred_cli_app.command("test", help="Send a test Block Kit message")
def test_send(ctx: typer.Context):
    """
    Send a hardcoded Block Kit message for testing, without database changes.
    """
    logger = ctx.obj.logger
    say = ctx.obj.say
    logger.info(f"Creating test Block Kit message...")

    blocks = BlockBuilder.build_single_todo_blocks(
        {
            "user_id": "foo",
            "todo_id": 9999,
            "todo_content": "Test Task",
            "status": "pending",
        }
    )

    # Send this Block Kit (default ephemeral)
    try:
        say(text="Block Kit Test Message", blocks=blocks)
    except Exception as e:
        logger.exception(f"Error posting TEST block kit")
        say(f"An error occurred while sending the test message: {e}")


@alfred_cli_app.command("help", help="Show help information")
def show_help(ctx: typer.Context):
    """
    Show help information.
    """
    logger = ctx.obj.logger
    say = ctx.obj.say
    logger.info("Showing help information...")
    help_text = help_string()
    say(f"*Alfred Bot Command Help:*\n```{help_text}```")
