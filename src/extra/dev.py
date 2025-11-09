# local devolopment, should disable in production

# SlackRequestHandler translates WSGI requests to Bolt's interface
# and builds WSGI response from Bolt's response.
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import request
from .flask_app import flask_app
from ..slack.app import app

handler = SlackRequestHandler(app)


# Register routes to Flask app
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    # handler runs App's dispatch method
    return handler.handle(request)
