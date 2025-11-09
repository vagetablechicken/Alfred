import os
import logging

from .utils.logger_config import setup_global_logger

from .task.engine_launcher import launch_engine_scheduler
from .slack.app import socket_mode_handler
# register
from .extra.flask_app import flask_app

# for dev, bind slack events to flask app
from .extra import dev

_ = dev  # to avoid unused import warning

if __name__ == "__main__":
    assert os.environ.get("SLACK_APP_TOKEN") is not None, "SLACK_APP_TOKEN is required!"

    setup_global_logger(log_file_name="alfred.log")
    logger = logging.getLogger(__name__)

    # if you need the bot user ID for any reason, try this
    # try:
    #     auth_response = app.client.auth_test()
    #     BOT_USER_ID = auth_response["user_id"]
    #     logger.info(f"Successfully authenticated as Bot User ID: {BOT_USER_ID}")
    # except Exception as e:
    #     logger.error(f"Error fetching bot user ID: {e}")
    #     logger.error(
    #         "Please check SLACK_BOT_TOKEN and bot permissions (auth:test scope)."
    #     )
    #     sys.exit(1)

    launch_engine_scheduler()

    socket_mode_handler.connect()  # Keep the Socket Mode client running but non-blocking
    flask_app.run(port=10443)
