# local development, should disable in production
from flask import request
from .flask_app import flask_app
from ..slack.app import socket_mode_handler


# Register routes to Flask app
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    # handler runs App's dispatch method
    return socket_mode_handler.handle(request)
