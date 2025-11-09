from datetime import datetime
from ..app import app
from ...task.task_engine import task_engine


@app.event("app_mention")
def handle_app_mention(event, client, logger):
    """
    You ask me to get some information when I am mentioned.
    I only talk to you, ephemeral messages.
    """
    message_text = event.get("text", "")
    logger.info(f"App mentioned with message: {message_text}")
    # TODO: simple command parsing, improve later
    if (
        message_text.lower().find("hi") != -1
        or message_text.lower().find("hello") != -1
    ):
        client.chat_postEphemeral(f"Hello there, <@{event['user']}>!")
    elif message_text.lower().find("list") != -1:
        todos = task_engine.get_todos(datetime.today().date())  # get all today's todos
        todo_list = (
            "\n".join([f"• {t[0]}" for t in todos]) if todos else "_No todos found._"
        )
        client.chat_postEphemeral(f"*Your Project TODOs today:* \n{todo_list}")
    else:
        help_message = (
            "Hi! I can help you with the following commands:\n"
            "• `hi` or `hello`: Greet me!\n"
            "• `list`: Get today's TODO list.\n"
            "Just mention me with one of these commands!"
        )
        client.chat_postEphemeral(help_message)
