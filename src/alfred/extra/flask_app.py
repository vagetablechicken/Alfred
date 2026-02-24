from datetime import datetime, timezone
from flask import Flask, make_response

from alfred.task.bulletin import Bulletin
from alfred.utils.format import format_templates, format_todos

flask_app = Flask(__name__)

_start_time = datetime.now(timezone.utc)


@flask_app.route("/", methods=["GET"])
def index():
    now = datetime.now(timezone.utc)
    uptime_seconds = int((now - _start_time).total_seconds())
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    return make_response(
        f"🟢 Alfred is online!\n"
        f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Uptime: {uptime_str}",
        200,
    )


@flask_app.route("/health", methods=["GET"])
def health():
    now = datetime.now(timezone.utc)
    return make_response(
        f"status: ok\ntime: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        200,
    )

# helpful extra api endpoint for checking or debugging
@flask_app.route("/todos", methods=["GET"])
def list_todos():
    todos = Bulletin().get_todos()
    if not todos:
        todo_list = "_No todos found._"
    else:
        todo_list = format_todos(todos)
    return make_response(f"*Your Project TODOs:* \n{todo_list}", 200)


@flask_app.route("/templates", methods=["GET"])
def list_templates():
    templates = Bulletin().get_templates()
    template_list = format_templates(templates)
    return make_response(f"*Your Project Templates:* \n{template_list}", 200)
