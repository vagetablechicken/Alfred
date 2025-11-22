from datetime import datetime, timedelta

from alfred.task.bulletin import Bulletin
from alfred.task.vault import get_vault
from alfred.task.vault.models import Todo, TodoStatus, TodoStatusLog


def test_complete_todo_records_status_and_log():
	bulletin = Bulletin()

	# create a template to satisfy foreign key
	template_id = bulletin.add_template(
		user_id="U_TEST",
		content="Complete me",
		cron="* * * * *",
		ddl_offset="1h",
		run_once=0,
	)

	vault = get_vault()
	now = datetime.now()
	remind_time = now
	ddl_time = now + timedelta(hours=1)

	# insert a pending todo directly using ORM
	with vault.session_scope() as session:
		todo = Todo(
			template_id=template_id,
			user_id="U_TEST",
			remind_time=remind_time,
			ddl_time=ddl_time,
			status=TodoStatus.PENDING,
		)
		session.add(todo)
		session.flush()
		todo_id = todo.id

	# mark completed
	bulletin.complete_todo(todo_id, now)

	# verify todo updated
	todo = bulletin.get_todo(todo_id)
	assert todo is not None
	assert todo["status"] == "completed"

	# verify log created
	logs = bulletin.get_todo_log(todo_id)
	assert len(logs) >= 1
	assert logs[-1]["new_status"] == "completed"
	assert logs[-1]["old_status"] == "pending"


def test_revert_todo_completion_sets_pending_and_logs():
	bulletin = Bulletin()

	template_id = bulletin.add_template(
		user_id="U_TEST2",
		content="Revert me",
		cron="* * * * *",
		ddl_offset="1h",
		run_once=0,
	)

	vault = get_vault()
	now = datetime.now()
	remind_time = now
	ddl_time = now + timedelta(hours=1)

	# insert a completed todo directly using ORM
	with vault.session_scope() as session:
		todo = Todo(
			template_id=template_id,
			user_id="U_TEST2",
			remind_time=remind_time,
			ddl_time=ddl_time,
			status=TodoStatus.COMPLETED,
		)
		session.add(todo)
		session.flush()
		todo_id = todo.id
		# insert an initial completion log to simulate prior completion
		log = TodoStatusLog(
			todo_id=todo_id,
			old_status=TodoStatus.PENDING,
			new_status=TodoStatus.COMPLETED,
			changed_at=now,
		)
		session.add(log)

	# revert completion
	bulletin.revert_todo_completion(todo_id, now)

	todo = bulletin.get_todo(todo_id)
	assert todo is not None
	assert todo["status"] == "pending"

	logs = bulletin.get_todo_log(todo_id)
	assert logs[-1]["new_status"] == "pending"
	assert logs[-1]["old_status"] == "completed"


def test_get_todos_with_date_filter():
	"""Test get_todos with date parameter to verify PostgreSQL compatibility"""
	bulletin = Bulletin()

	# create a template
	template_id = bulletin.add_template(
		user_id="U_TEST3",
		content="Date filter test",
		cron="* * * * *",
		ddl_offset="1h",
		run_once=0,
	)

	vault = get_vault()
	now = datetime.now()
	today = now.date()
	tomorrow = today + timedelta(days=1)

	# insert todos for today and tomorrow
	with vault.session_scope() as session:
		todo_today = Todo(
			template_id=template_id,
			user_id="U_TEST3",
			remind_time=now,
			ddl_time=now + timedelta(hours=1),
			status=TodoStatus.PENDING,
		)
		todo_tomorrow = Todo(
			template_id=template_id,
			user_id="U_TEST3",
			remind_time=now + timedelta(days=1),
			ddl_time=now + timedelta(days=1, hours=1),
			status=TodoStatus.PENDING,
		)
		session.add(todo_today)
		session.add(todo_tomorrow)
		session.flush()
		todo_today_id = todo_today.id
		todo_tomorrow_id = todo_tomorrow.id

	# test get_todos with date parameter (date object)
	todos_today = bulletin.get_todos(today)
	assert len(todos_today) == 1
	assert todos_today[0]["todo_id"] == todo_today_id
	assert todos_today[0]["user_id"] == "U_TEST3"

	# test get_todos with date parameter (string)
	todos_tomorrow = bulletin.get_todos(tomorrow.isoformat())
	assert len(todos_tomorrow) == 1
	assert todos_tomorrow[0]["todo_id"] == todo_tomorrow_id

	# test get_todos without date parameter (should get all)
	todos_all = bulletin.get_todos()
	assert len(todos_all) == 2
