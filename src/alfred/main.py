from alfred.utils.config import load_config, setup_global_logger

from alfred.task.engine_launcher import launch_engine_scheduler
from alfred.slack.patrol_launcher import launch_patrol_scheduler
from alfred.slack.app import socket_mode_handler
from alfred.slack import listeners
_ = listeners  # to avoid unused import warning

# register
from alfred.extra.flask_app import flask_app

# for dev, bind slack events to flask app
from alfred.extra import dev

_ = dev  # to avoid unused import warning


def alfred_in():
    config = load_config()
    logging_config = config.get("logging", {})
    console_level = logging_config.get("console_level", "INFO").upper()
    file_level = logging_config.get("file_level", "DEBUG").upper()
    log_file = config.get("log_file", "alfred.log")
    setup_global_logger(console_level=console_level, file_level=file_level, log_file_name=log_file)

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
    launch_patrol_scheduler()

    socket_mode_handler.connect()  # Keep the Socket Mode client running but non-blocking
    flask_app.run(port=10443)


if __name__ == "__main__":
    alfred_in()
