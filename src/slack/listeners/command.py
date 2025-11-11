import logging
from ..app import app
from ...task.task_engine import task_engine


@app.command("/alfred")
def handle_alfred_command(ack, body, client, logger, say):
    """
    Handle /alfred command
    'say' is ephemeral by default in commands
    """
    # Immediately ACK (within 3 seconds)
    ack()

    user_id = body["user_id"]
    text = body.get("text", "").strip()
    logger.info(f"User {user_id} triggered /alfred with: {text}")

    try:
        # TODO: interactive template addition
        if text.lower().startswith("add template"):
            args = text[len("add template ") :].strip()
            handle_add_template(args, user_id, logger, say)

        elif text.lower().startswith("list"):
            args = text[len("list ") :].strip()
            handle_list(args, user_id, logger, say)

        elif text.lower().startswith("log"):
            args = text[len("log ") :].strip()
            handle_log(args, user_id, logger, say)

        elif text.lower().startswith("test"):
            # (Hidden test command) Directly reply with a todo Block Kit message not in the library
            generate_test_todo_block(user_id, logger, say)

        else:
            # (Help information)
            say(
                "*Alfred Bot Command Help:*\n"
                "• `/alfred add template <user_id> <name> <cron> <bias> [<run_once>]`\n"
                "  run_once is optional, 1 = run once then disable, 0 = run periodically, default is 0\n"
                "  (Example: `/alfred add template 'U0xxx' 'Review' '0 9 * * 1-5' '1h' '1'`)\n"
                "• `/alfred list [todos|templates]`\n"
                "  (Default is `todos`)\n"
                "• `/alfred log <todo_id>`\n"
                "  (Mark your todo as 'completed')"
            )
    except Exception as e:
        logger.error(f"Unhandled error in /alfred: {e}")
        say(f"An unexpected error occurred: {e}")


def handle_add_template(args, user_id, logger, say):
    """Handle the command to add task template"""
    parts = args.split()
    if len(parts) < 4:
        say("Usage: /alfred add template <user_id> <name> <cron> <ddl_offset> [<run_once>]")
        return

    target_user_id = parts[0]
    name = parts[1]
    cron = parts[2]
    ddl_offset = parts[3]
    run_once = int(parts[4]) if len(parts) > 4 else 0

    template_id = task_engine.add_template(
        target_user_id, name, cron, ddl_offset, run_once
    )
    logger.info(
        f"User <@{user_id}> added template {template_id} for <@{target_user_id}>"
    )
    say(f"Template '{name}' added for <@{target_user_id}> with ID {template_id}.")


def handle_list(args, user_id, logger: logging.Logger, say):
    """Handle the command to list todos or templates"""
    list_type = args.lower() if args else "todos"
    if list_type == "todos":
        # admin may want to see all todos
        todos = task_engine.get_todos()
        if not todos:
            say("No TODOs.")
            return
        todo_list = "\n".join([f"• ID {t[1]}: {t[0]}" for t in todos])
        logger.debug(f"Listing todos: {todo_list}")
        say(f"*TODOs:*\n{todo_list}")
    elif list_type == "templates":
        templates = task_engine.get_templates()
        if not templates:
            say("No task templates.")
            return
        template_list = "\n".join(
            [
                f"• ID {t[0]}: {t[2]} (Cron: {t[3]}, Bias: {t[4]}, Run Once: {t[5]})"
                for t in templates
            ]
        )
        logger.debug(f"Listing templates: {template_list}")
        say(f"*Task Templates:*\n{template_list}")
    else:
        say("Unknown list type. Use 'todos' or 'templates'.")


def handle_log(args, user_id, logger, say):
    """Handle the command to mark todo as completed"""
    parts = args.split()
    if len(parts) != 1:
        say("Usage: /alfred log <todo_id>")
        return

    todo_id = parts[0]
    todo_log = task_engine.get_todo_log(todo_id)
    logger.debug(f"Fetched log for todo_id {todo_id}: {todo_log}")
    if not todo_log:
        say(f"No TODO found with ID {todo_id}.")
        return
    # 1. Prepare the log string first
    log_string = "\n".join(todo_log)

    # 2. Now the f-string is simple and readable
    say(f"""TODO log for ID {todo_id}:\n{log_string}""")


def generate_test_todo_block(user_id: str, logger: logging.Logger, say):
    """
    Send a hardcoded Block Kit message for testing, without database changes.
    """
    logger.info(f"User {user_id} triggered a Block Kit test.")

    todo_id = 99999
    section_block_id = f"todo_{todo_id}_section"
    action_block_id = f"todo_{todo_id}_actions"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*This is a todo item for testing:*"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "block_id": section_block_id,
            "text": {
                "type": "mrkdwn",
                "text": f"*[ID: {todo_id}]* `Test Task`\n*Status*: pending",
            },
        },
        {
            "type": "actions",
            "block_id": action_block_id,
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Log (Complete)"},
                    "action_id": "log_todo_button",
                    "value": str(todo_id),
                    "style": "primary",
                }
            ],
        },
    ]

    # Send this Block Kit (default ephemeral)
    try:
        say(text="Block Kit Test Message", blocks=blocks)
    except Exception as e:
        logger.error(f"Error posting TEST block kit: {e}")
