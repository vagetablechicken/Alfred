from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from ..task.task_engine import task_engine


def patrol_job():
    current_time = datetime.now()
    # read from engine, if tasks are due, send reminders
    todos = task_engine.get_todos(current_time.date())
    normal_reminders = [
        todo
        for todo in todos
        if todo["reminder_time"] <= current_time and todo["ddl_time"] > current_time
    ]
    overdue_reminders = [todo for todo in todos if todo["ddl_time"] <= current_time]
    # TODO: send reminders via Slack API


def launch_patrol_scheduler():
    # only 1 worker thread
    executors = {"default": ThreadPoolExecutor(max_workers=1)}

    scheduler = BackgroundScheduler(executors=executors)

    try:
        scheduler.add_job(
            func=patrol_job,
            trigger="interval",
            seconds=60,  # run every minute
            id="butler_patrol_job",
            replace_existing=True,
            misfire_grace_time=60,
        )

        scheduler.start()
        return True
    except Exception as e:
        print(f"Error starting scheduler: {e}")
        scheduler.shutdown()
        return False
