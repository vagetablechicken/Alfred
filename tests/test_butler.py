from datetime import datetime, timedelta, time

from alfred.slack.butler import Butler
from alfred.task.vault import get_vault
from alfred.task.vault.models import Todo, TodoStatus


def test_gather_notify_blocks_with_normal_and_overdue():
    """Test gather_notify_blocks returns blocks for normal and overdue todos"""
    butler = Butler()
    
    # create a template
    template_id = butler.add_template(
        user_id="U_TEST_NOTIFY",
        content="Test notification",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    # create normal todo (remind_time <= now < ddl_time)
    normal_remind_time = now - timedelta(minutes=10)
    normal_ddl_time = now + timedelta(minutes=50)
    
    # create overdue todo (ddl_time <= now)
    overdue_remind_time = now - timedelta(hours=2)
    overdue_ddl_time = now - timedelta(minutes=30)
    
    with vault.session_scope() as session:
        normal_todo = Todo(
            template_id=template_id,
            user_id="U_TEST_NOTIFY",
            remind_time=normal_remind_time,
            ddl_time=normal_ddl_time,
            status=TodoStatus.PENDING,
        )
        overdue_todo = Todo(
            template_id=template_id,
            user_id="U_TEST_NOTIFY",
            remind_time=overdue_remind_time,
            ddl_time=overdue_ddl_time,
            status=TodoStatus.PENDING,
        )
        session.add(normal_todo)
        session.add(overdue_todo)
        session.flush()
        normal_todo_id = normal_todo.id
        overdue_todo_id = overdue_todo.id
    
    # gather blocks
    with butler.gather_notify_blocks() as blocks:
        # should have blocks for both normal and overdue
        assert len(blocks) > 0
        # check that blocks contain both todos
        block_text = str(blocks)
        assert "U_TEST_NOTIFY" in block_text
    
    # verify sent_notifies updated
    assert normal_todo_id in butler.sent_notifies["normal"]
    assert overdue_todo_id in butler.sent_notifies["overdue"]
    
    # second call should return empty blocks (already sent)
    with butler.gather_notify_blocks() as blocks:
        assert len(blocks) == 0


def test_gather_notify_blocks_filters_completed_todos():
    """Test gather_notify_blocks skips completed todos"""
    butler = Butler()
    
    template_id = butler.add_template(
        user_id="U_TEST_COMPLETED",
        content="Completed todo",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    remind_time = now - timedelta(minutes=10)
    ddl_time = now + timedelta(minutes=50)
    
    # create completed todo
    with vault.session_scope() as session:
        completed_todo = Todo(
            template_id=template_id,
            user_id="U_TEST_COMPLETED",
            remind_time=remind_time,
            ddl_time=ddl_time,
            status=TodoStatus.COMPLETED,
        )
        session.add(completed_todo)
    
    # should return empty blocks
    with butler.gather_notify_blocks() as blocks:
        assert len(blocks) == 0


def test_gather_end_of_day_summary():
    """Test gather_end_of_day_summary returns blocks after summary_time"""
    butler = Butler()
    
    # set summary time to past (so it triggers)
    butler.summary_time = time(hour=0, minute=0)
    
    # create a template and todo
    template_id = butler.add_template(
        user_id="U_TEST_SUMMARY",
        content="Summary test",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    with vault.session_scope() as session:
        todo = Todo(
            template_id=template_id,
            user_id="U_TEST_SUMMARY",
            remind_time=now,
            ddl_time=now + timedelta(hours=1),
            status=TodoStatus.PENDING,
        )
        session.add(todo)
    
    # gather summary blocks
    with butler.gather_end_of_day_summary() as blocks:
        # should have summary blocks
        assert len(blocks) > 0
        block_text = str(blocks)
        assert "U_TEST_SUMMARY" in block_text or "summary" in block_text.lower()
    
    # verify sent_summaries updated
    assert now.date() in butler.sent_summaries
    
    # second call should return empty blocks (already sent)
    with butler.gather_end_of_day_summary() as blocks:
        assert len(blocks) == 0


def test_gather_end_of_day_summary_before_time():
    """Test gather_end_of_day_summary returns empty blocks before summary_time"""
    butler = Butler()
    
    # set summary time to future (so it doesn't trigger)
    butler.summary_time = time(hour=23, minute=59)
    
    # create a template and todo
    template_id = butler.add_template(
        user_id="U_TEST_NO_SUMMARY",
        content="No summary yet",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    with vault.session_scope() as session:
        todo = Todo(
            template_id=template_id,
            user_id="U_TEST_NO_SUMMARY",
            remind_time=now,
            ddl_time=now + timedelta(hours=1),
            status=TodoStatus.PENDING,
        )
        session.add(todo)
    
    # should return empty blocks (before summary time)
    with butler.gather_end_of_day_summary() as blocks:
        assert len(blocks) == 0


def test_mark_todo_complete():
    """Test mark_todo_complete marks a todo as completed"""
    butler = Butler()
    
    template_id = butler.add_template(
        user_id="U_TEST_COMPLETE",
        content="Complete me",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    with vault.session_scope() as session:
        todo = Todo(
            template_id=template_id,
            user_id="U_TEST_COMPLETE",
            remind_time=now,
            ddl_time=now + timedelta(hours=1),
            status=TodoStatus.PENDING,
        )
        session.add(todo)
        session.flush()
        todo_id = todo.id
    
    # mark complete
    butler.mark_todo_complete(todo_id)
    
    # verify status changed
    updated_todo = butler.get_todo(todo_id)
    assert updated_todo["status"] == "completed"


def test_mark_todo_undo():
    """Test mark_todo_undo reverts a completed todo to pending"""
    butler = Butler()
    
    template_id = butler.add_template(
        user_id="U_TEST_UNDO",
        content="Undo me",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    with vault.session_scope() as session:
        todo = Todo(
            template_id=template_id,
            user_id="U_TEST_UNDO",
            remind_time=now,
            ddl_time=now + timedelta(hours=1),
            status=TodoStatus.COMPLETED,
        )
        session.add(todo)
        session.flush()
        todo_id = todo.id
    
    # undo completion
    butler.mark_todo_undo(todo_id)
    
    # verify status changed back to pending
    updated_todo = butler.get_todo(todo_id)
    assert updated_todo["status"] == "pending"


def test_build_single_todo_blocks():
    """Test build_single_todo_blocks returns blocks for a specific todo"""
    butler = Butler()
    
    template_id = butler.add_template(
        user_id="U_TEST_SINGLE",
        content="Single todo",
        cron="* * * * *",
        ddl_offset="1h",
        run_once=0,
    )
    
    vault = get_vault()
    now = datetime.now()
    
    with vault.session_scope() as session:
        todo = Todo(
            template_id=template_id,
            user_id="U_TEST_SINGLE",
            remind_time=now,
            ddl_time=now + timedelta(hours=1),
            status=TodoStatus.PENDING,
        )
        session.add(todo)
        session.flush()
        todo_id = todo.id
    
    # build blocks
    blocks = butler.build_single_todo_blocks(todo_id)
    
    # verify blocks exist and contain todo info
    assert len(blocks) > 0
    block_text = str(blocks)
    assert "U_TEST_SINGLE" in block_text or "Single todo" in block_text
