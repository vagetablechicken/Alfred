import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

assert os.environ.get(
    "SLACK_BOT_TOKEN"
), "SLACK_BOT_TOKEN environment variable is required."
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# SlackRequestHandler translates WSGI requests to Bolt's interface
# and builds WSGI response from Bolt's response.

# Create an app-level token with connections:write scope
assert os.environ.get(
    "SLACK_APP_TOKEN"
), "SLACK_APP_TOKEN environment variable is required."
socket_mode_handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
