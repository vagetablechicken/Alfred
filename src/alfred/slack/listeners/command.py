from datetime import datetime
import enum
from croniter import croniter
import re
import typer
import shlex

from alfred.slack.block_builder import BlockBuilder
from alfred.utils.config import get_slack_admin
from alfred.utils.format import build_add_template_view, format_templates, format_todo_logs, format_todos

from alfred.slack.app import app
from alfred.slack.butler import butler


@app.command("/alfred")
def handle_alfred_command(ack, body, client, logger, say):
    """
    Handle /alfred command
    Use client.chat_postEphemeral() to send messages visible only to the user
    """
    # Immediately ACK (within 3 seconds)
    ack()

    user_id = body["user_id"]
    channel_id = body["channel_id"]
    # text is no /alfred prefix
    text = body.get("text", "").strip()
    logger.info(f"User {user_id} triggered /alfred with: {text}")

    def say_ephemeral(message: str = None, *, blocks=None):
        """Send ephemeral message visible only to the command user"""
        assert not (
            message is None and blocks is None
        ), "Either message or blocks must be provided"
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=message, blocks=blocks
        )

    if (admin_list := get_slack_admin()) and (user_id not in admin_list):
        say_ephemeral("❌ *Permission Denied*: You are not an admin.")
        logger.warning(f"User {user_id} is not an admin. Permission denied.")
        return

    try:
        args_list = shlex.split(text)
        logger.debug(f"Parsed args: {args_list}")
        # bind logger and say to AppState for Typer commands
        class AppState:
            def __init__(self, logger, say_ephemeral, say):
                self.logger = logger
                self.say_ephemeral = say_ephemeral
                self.say = say
                self.trigger_id = body.get("trigger_id")
        alfred_cli_app(args_list, obj=AppState(logger, say_ephemeral, say), standalone_mode=False)
    except typer.BadParameter as e:
        # Typer validation error
        logger.exception(f"Typer parameter error: {e}")
        say_ephemeral(f"❌ *Parameter Error*:\n`{e}`")
    except SystemExit as e:
        # Typer exits on --help or errors
        if e.code == 0:
            logger.info("\n--- Typer help info (captured) ---")
            # normal exit
        else:
            logger.info("\n--- Typer parameter error (captured) ---")
            logger.info("  (Tip: may be missing required parameters)")
            say_ephemeral(
                f"❌ *Parameter Error*:\n`Please check your command format or use /alfred help for help`"
            )
    except Exception as e:
        logger.exception(f"Unknown error: {e}")
        say_ephemeral(f"❌ *Error occurred*:\n`{e}`")


# validators for Typer arguments
def validate_cron(value: str) -> str:
    """Check if value is a valid Cron expression"""
    if not croniter.is_valid(value):
        raise typer.BadParameter(f"'{value}' is not a valid cron expression")
    # print(f"Validated Cron: {value}")
    return value


# TODO(hw): ref bulletin offset validation
def validate_duration(value: str) -> str:
    """
    Validate offset field.
    Parse '1h', '3m', '5m', '1d' or '1' (represents 1d).
    """
    value_str = str(value).strip().lower()

    match = re.match(r"^(\d+)([smhd])$", value_str)
    if match:
        # Validation passed (e.g., '1h', '3m')
        # print(f"Validated Duration: {value_str}")
        return value_str

    match_int = re.match(r"^(\d+)$", value_str)
    if match_int:
        # Validation passed (e.g., '1', assumed as '1d')
        # print(f"Validated Duration: {value_str} (assumed days)")
        return value_str

    raise typer.BadParameter(f"Unable to parse duration/bias format: '{value}'")


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


add_app = typer.Typer(help="Add (e.g., 'template')")
alfred_cli_app.add_typer(add_app, name="add")

# add will create interactive modal
@add_app.callback(invoke_without_command=True)
def add_main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.obj.logger.info("No subcommand provided for 'add'. Opening modal...")
        ctx.obj.client.views_open(
            trigger_id=ctx.obj.trigger_id,
            view=build_add_template_view(view="submit_cron_template"),
        )
    # subcommand will handle the rest if provided


# add template command for developer
@add_app.command(
    "template",
    help="• /alfred add template <user_id> <name> <cron> <offset> [<run_once>]",
)
def add_template(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="User ID (e.g., 'U0xxx')"),
    name: str = typer.Argument(..., help="Template name (e.g., 'Review')"),
    cron: str = typer.Argument(..., callback=validate_cron, help="Cron expression"),
    offset: str = typer.Argument(
        ..., callback=validate_duration, help="Reminder interval/offset (e.g., '1h')"
    ),
    # optional argument with default
    run_once: int = typer.Argument(0, help="1 = run once, 0 = periodic (default: 0)"),
):
    """
    Add a task template.
    """
    template_id = butler.add_template(user_id, name, cron, offset, run_once)
    ctx.obj.logger.info(
        f"User <@{user_id}> added template {template_id} for <@{user_id}>"
    )
    ctx.obj.say_ephemeral(f"✅ Added template ID {template_id} for <@{user_id}>.")


# --- list command ---
@alfred_cli_app.command(
    "list", help="• /alfred list [todos|templates] (Default is 'todos')"
)
def list_items(
    ctx: typer.Context,
    category: ListCategory = typer.Argument(
        ListCategory.todos,
        case_sensitive=False,
        help="Type of items to list (todos or templates)",
    ),
):
    """
    List todos or templates.
    """
    logger = ctx.obj.logger
    say_ephemeral = ctx.obj.say_ephemeral
    logger.info(f"Category: {category.value}")  # 'todos' or 'templates'

    if category == ListCategory.todos:
        logger.info("Fetching all active todos...")
        # admin may want to see all todos
        todos = butler.get_todos()
        todo_list = format_todos(todos)
        logger.debug(f"Listing todos: {todo_list}")
        say_ephemeral(f"*TODOs:*\n{todo_list}")
    elif category == ListCategory.templates:
        logger.info("Fetching all templates...")
        templates = butler.get_templates()
        template_list = format_templates(templates)
        logger.debug(f"Listing templates: {template_list}")
        say_ephemeral(f"*Task Templates:*\n{template_list}")


# --- log command ---
@alfred_cli_app.command(
    "log", help="• /alfred log <todo_id> (Show log for a specific todo ID)"
)
def log_todo(
    ctx: typer.Context,
    todo_id: str = typer.Argument(..., help="TODO ID to view log"),
):
    """
    Show log for a specific todo.
    """
    logger = ctx.obj.logger
    say_ephemeral = ctx.obj.say_ephemeral
    logger.info(f"Getting log for todo_id: {todo_id}")

    todo_log = butler.get_todo_log(todo_id)
    log_string = format_todo_logs(todo_log)
    logger.debug(f"Fetched log for todo_id {todo_id}:\n{log_string}")
    say_ephemeral(f"""TODO log for ID {todo_id}:\n{log_string}""")


@alfred_cli_app.command("test", help="Send a test Block Kit message")
def test_send(ctx: typer.Context):
    """
    Send a hardcoded Block Kit message for testing, without database changes.
    This should send a public message visible to the channel.
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
            "remind_time": datetime.strptime(
                "2020-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"
            ),
            "ddl_time": datetime.strptime("2020-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"),
        }
    )

    # Send this Block Kit message publicly
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
    say_ephemeral = ctx.obj.say_ephemeral
    logger.info("Showing help information...")
    help_text = help_string()
    say_ephemeral(f"*Alfred Bot Command Help:*\n```{help_text}```")
