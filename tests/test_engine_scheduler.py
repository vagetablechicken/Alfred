from alfred.task.bulletin import Bulletin
from alfred.task.engine_launcher import launch_engine_scheduler

import time

def test_task_runs_in_background_and_completes():
    assert launch_engine_scheduler(seconds=10)  # run every second for testing
    bulletin = Bulletin()
    # add a template
    template_id = bulletin.add_template(
        user_id="U_TEST",
        todo_content="Test Task",
        cron="*/1 * * * *",  # every minute
        ddl_offset="5s",
        run_once=0,
    )
    assert template_id is not None

    time.sleep(20)  # wait for 20 seconds to ensure at least one run
    # at least one task should be created
    todos = bulletin.get_todos()
    assert any(todo["template_id"] == template_id for todo in todos)
