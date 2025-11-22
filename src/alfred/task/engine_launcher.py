from datetime import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from .task_engine import run_scheduler

logger = logging.getLogger(__name__)

def task_engine_job():
    try:
        current_time = datetime.now()
        run_scheduler(current_time)
    except Exception as e:
        logger.exception(f"Error in task engine job: {e}")


def launch_engine_scheduler(seconds: int = 60) -> bool:
    # only 1 worker thread
    executors = {"default": ThreadPoolExecutor(max_workers=1)}

    scheduler = BackgroundScheduler(executors=executors)

    try:
        scheduler.add_job(
            func=task_engine_job,
            trigger="interval",
            seconds=seconds,  # default every 60 seconds, if in testing can set to smaller value
            id="task_engine_job",
            replace_existing=True,
            misfire_grace_time=60,
        )

        scheduler.start()
        return True
    except Exception as e:
        logger.exception(f"Error starting scheduler: {e}")
        scheduler.shutdown()
        return False
