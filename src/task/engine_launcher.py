from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from task_engine import task_engine


def task_engine_job():
    current_time = datetime.now()
    task_engine.run_scheduler(current_time)
    task_engine.run_escalator(current_time)


def launch_engine_scheduler():
    # only 1 worker thread
    executors = {"default": ThreadPoolExecutor(max_workers=1)}

    scheduler = BackgroundScheduler(executors=executors)

    try:
        scheduler.add_job(
            func=task_engine_job,
            trigger="interval",
            seconds=60,  # run every minute
            id="task_engine_job",
            replace_existing=True,
            misfire_grace_time=60,
        )

        scheduler.start()
        return True
    except Exception as e:
        print(f"Error starting scheduler: {e}")
        scheduler.shutdown()
        return False
