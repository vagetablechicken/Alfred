from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from .butler import butler
from .app import app
from ..utils.config import get_slack_channel

import logging

logger = logging.getLogger(__name__)


def patrol_job():
    # read from engine, if tasks are due, send reminders
    with butler.gather_notify_blocks() as blocks:
        if not blocks:
            # nothing to notify
            return
        res = app.client.chat_postMessage(channel=get_slack_channel(), blocks=blocks, text="任务提醒")
        if not res["ok"]:
            raise Exception(f"Slack API error: {res}")

    # 下班前发一个总结
    with butler.gather_end_of_day_summary() as blocks:
        if not blocks:
            return
        res = app.client.chat_postMessage(channel=get_slack_channel(), blocks=blocks, text="今日任务总结")
        if not res["ok"]:
            raise Exception(f"Slack API error: {res}")


def launch_patrol_scheduler(seconds=60):
    # only 1 worker thread
    executors = {"default": ThreadPoolExecutor(max_workers=1)}
    scheduler = BackgroundScheduler(executors=executors)

    try:
        scheduler.add_job(
            func=patrol_job,
            trigger="interval",
            seconds=seconds,  # run every minute
            id="butler_patrol_job",
            replace_existing=True,
            misfire_grace_time=60,
        )

        scheduler.start()
        return True
    except Exception as e:
        logger.exception(f"Error starting scheduler: {e}")
        scheduler.shutdown()
        return False
