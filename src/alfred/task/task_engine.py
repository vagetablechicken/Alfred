
from datetime import datetime

from .bulletin import Bulletin

_bulletin = Bulletin()


def run_scheduler(current_time: datetime | str):
    """Scheduler to create todos based on active templates."""
    _bulletin.schedule_todos(current_time)
