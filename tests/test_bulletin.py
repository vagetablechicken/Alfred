from datetime import datetime, timedelta

from alfred.task.bulletin import Bulletin
from alfred.task.vault import get_vault
from alfred.task.vault.models import Todo, TodoStatus, TodoStatusLog


def test_complete_todo_records_status_and_log():
	bulletin = Bulletin()

	# create a template to satisfy foreign key
	template_id = bulletin.add_template(
		user_id="U_TEST",
		todo_content="Complete me",
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
		todo_content="Revert me",
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
