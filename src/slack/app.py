import os
from slack_bolt import App

assert os.environ.get(
    "SLACK_BOT_TOKEN"
), "SLACK_BOT_TOKEN environment variable is required."
app = App(token=os.environ["SLACK_BOT_TOKEN"])


