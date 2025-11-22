from flask import Flask, make_response

from alfred.task.bulletin import Bulletin
from alfred.utils.format import format_templates, format_todos

flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def index():
    return make_response("Alfred is at work!", 200)

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
