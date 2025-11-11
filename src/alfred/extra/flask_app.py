from flask import Flask, make_response

from ..task import task_engine

flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def index():
    return make_response("Alfred is at work!", 200)

# helpful extra api endpoint for checking or debugging
@flask_app.route("/todos", methods=["GET"])
def list_todos():
    todos = task_engine.instance.get_todos()
    todo_list = (
        "\n".join([f"• {t[0]}" for t in todos]) if todos else "_No todos found._"
    )
    return make_response(f"*Your Project TODOs today:* \n{todo_list}", 200)


@flask_app.route("/templates", methods=["GET"])
def list_templates():
    templates = task_engine.instance.get_templates()
    template_list = (
        "\n".join([f"• {t[0]}" for t in templates])
        if templates
        else "_No templates found._"
    )
    return make_response(f"*Your Project Templates:* \n{template_list}", 200)
