import pytest
from datetime import datetime, timedelta

from alfred.task.bulletin import Bulletin
from alfred.task.vault import LockedSqliteVault


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

	vault = LockedSqliteVault()
	now = datetime.now()
	remind_iso = now.isoformat()
	ddl_iso = (now + timedelta(hours=1)).isoformat()

	# insert a pending todo directly
	with vault.transaction() as cur:
		cur.execute(
			"INSERT INTO todos (template_id, user_id, remind_time, ddl_time, status) VALUES (?, ?, ?, ?, ?)",
			(template_id, "U_TEST", remind_iso, ddl_iso, "pending"),
		)
		todo_id = cur.lastrowid

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

	vault = LockedSqliteVault()
	now = datetime.now()
	remind_iso = now.isoformat()
	ddl_iso = (now + timedelta(hours=1)).isoformat()

	# insert a completed todo directly
	with vault.transaction() as cur:
		cur.execute(
			"INSERT INTO todos (template_id, user_id, remind_time, ddl_time, status) VALUES (?, ?, ?, ?, ?)",
			(template_id, "U_TEST2", remind_iso, ddl_iso, "completed"),
		)
		todo_id = cur.lastrowid
		# insert an initial completion log to simulate prior completion
		cur.execute(
			"INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)",
			(todo_id, "pending", "completed", now.isoformat()),
		)

	# revert completion
	bulletin.revert_todo_completion(todo_id, now)

	todo = bulletin.get_todo(todo_id)
	assert todo is not None
	assert todo["status"] == "pending"

	logs = bulletin.get_todo_log(todo_id)
	assert logs[-1]["new_status"] == "pending"
	assert logs[-1]["old_status"] == "completed"

