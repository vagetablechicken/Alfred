from task.engine_launcher import launch_engine_scheduler
from task.task_engine import task_engine
import time

def test_task_runs_in_background_and_completes():
    assert task_engine.db_file.endswith("test_tasks.db")
    
    assert launch_engine_scheduler(seconds=1)  # run every second for testing

    # add a template
    template_id = task_engine.add_template(
        user_id="U_TEST",
        todo_content="Test Task",
        cron="*/1 * * * *",  # every minute
        ddl_offset="5s",
        run_once=0,
    )
    assert template_id is not None
    # wait for a few seconds to let the scheduler run
    time.sleep(5)  # wait for 5 seconds to ensure at least one run
    # at least one task should be created
    todos = task_engine.get_todos()
    assert any(todo["template_id"] == template_id for todo in todos)

