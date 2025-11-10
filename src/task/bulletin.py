from datetime import datetime
import logging
import sqlite3

from .database.archive import get_archive  # import the singleton Archive instance


class Bulletin:
    """
    Read raw meta data from singleton Archive instance. Manage templates and todos.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def complete_todo(self, todo_id: int, current_time: datetime | str):
        """User completes a todo"""
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Completing Todo {todo_id} at {current_time} ---")
        archive = get_archive()
        try:
            result = archive.read(
                "SELECT status FROM todos WHERE todo_id = ?", (todo_id,)
            )
            old_status = result[0]
            if old_status in ("completed", "revoked"):
                self.logger.info(
                    f"Todo {todo_id} is already in a final state ({old_status})."
                )
                return

            # update in one transaction
            with archive:
                archive.write(
                    "UPDATE todos SET status = 'completed', updated_at = ? WHERE todo_id = ?",
                    (current_time.isoformat(), todo_id),
                )
                archive.write(
                    "INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, ?, 'completed', ?)",
                    (todo_id, old_status, current_time.isoformat()),
                )
            self.logger.info(f"COMPLETED Todo {todo_id} (was {old_status})")
        except sqlite3.Error as e:
            self.logger.error(f"ERROR completing Todo {todo_id}: {e}")

    def revert_task_completion(
        self, todo_id: int, current_time: datetime.datetime | str
    ):
        """user reverts a completed task back to pending/escalated"""
        if isinstance(current_time, str):
            current_time = datetime.datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Reverting Todo {todo_id} at {current_time} ---")
        try:
            with self.db as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT status, ddl_time FROM todos WHERE todo_id = ?", (todo_id,)
                )
                result = cur.fetchone()

                if not result:
                    self.logger.error(f"ERROR: Todo {todo_id} not found.")
                    return
                old_status, ddl_time_str = result

                if old_status != "completed":
                    self.logger.error(
                        f"ERROR: Todo {todo_id} is not 'completed'. Cannot revert."
                    )
                    return

                # we determine new status based on ddl_time
                ddl_time = datetime.datetime.fromisoformat(ddl_time_str)
                new_status = "escalated" if current_time >= ddl_time else "pending"

                cur.execute(
                    "UPDATE todos SET status = ?, updated_at = ? WHERE todo_id = ?",
                    (new_status, current_time.isoformat(), todo_id),
                )
                cur.execute(
                    "INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, 'completed', ?, ?)",
                    (todo_id, new_status, current_time.isoformat()),
                )
                self.logger.info(
                    f"REVERTED Todo {todo_id} from 'completed' back to '{new_status}'"
                )
        except sqlite3.Error as e:
            self.logger.error(f"ERROR reverting Todo {todo_id}: {e}")

    def set_template_active_status(
        self, template_id: int, is_active: bool, current_time: datetime.datetime | str
    ):
        """admin activates/deactivates a template"""
        if isinstance(current_time, str):
            current_time = datetime.datetime.fromisoformat(current_time)
        status_str = "Activating" if is_active else "Deactivating"
        self.logger.info(
            f"--- [ADMIN] {status_str} Template {template_id} at {current_time} ---"
        )

        try:
            with self.db as conn:
                cur = conn.cursor()

                # update template active status
                cur.execute(
                    "UPDATE todo_templates SET is_active = ? WHERE template_id = ?",
                    (1 if is_active else 0, template_id),
                )

                tasks_to_revoke = []

                if not is_active:
                    # if deactivating, revoke all pending/escalated tasks from this template
                    cur.execute(
                        """
                        SELECT todo_id, status FROM todos 
                        WHERE template_id = ? AND status IN ('pending', 'escalated')
                    """,
                        (template_id,),
                    )

                    tasks_to_revoke = cur.fetchall()
                    if not tasks_to_revoke:
                        self.logger.info("No active todos to revoke.")

                    for todo_id, old_status in tasks_to_revoke:
                        self.logger.info(
                            f"REVOKING Todo {todo_id} (was {old_status})..."
                        )
                        # update todos
                        cur.execute(
                            """
                            UPDATE todos SET status = 'revoked', updated_at = ?
                            WHERE todo_id = ?
                        """,
                            (current_time.isoformat(), todo_id),
                        )

                        # insert into todo_status_logs
                        cur.execute(
                            """
                            INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
                            VALUES (?, ?, 'revoked', ?)
                        """,
                            (todo_id, old_status, current_time.isoformat()),
                        )

                self.logger.info(
                    f"Successfully set Template {template_id} active status to {is_active}"
                )
                if not is_active and tasks_to_revoke:
                    self.logger.info(
                        f"Revoked {len(tasks_to_revoke)} associated tasks."
                    )

        except sqlite3.Error as e:
            self.logger.error(f"ERROR changing template status: {e}")

    def add_template(self, user_id, todo_content, cron, ddl_offset, run_once=0):
        """
        Add a new task template for a todo.
        Returns the template_id of the newly created template.
        """
        self.logger.info(f"Adding template for {user_id}: {todo_content}")
        with self.db as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
                (user_id, todo_content, cron, ddl_offset, run_once),
            )
            return cur.lastrowid  # template_id

    def db_content(self):
        """
        Return string representation of all tables for debugging.
        """
        return self.db.full_content()

    def get_templates(self):
        """get all todo templates"""
        self.logger.info(f"[QUERY] Getting all todo templates")
        try:
            with self.db as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        template_id,
                        user_id,
                        todo_content,
                        cron,
                        ddl_offset,
                        is_active,
                        run_once,
                        created_at
                    FROM todo_templates
                    ORDER BY template_id
                    """
                )

                results = cur.fetchall()
                return results
        except sqlite3.Error as e:
            self.logger.info(f"ERROR querying todo templates: {e}")
            return []

    def get_todos(self, query_date: datetime.date | str = None):
        """get todos for a specific date (YYYY-MM-DD) or all if None"""
        if query_date and isinstance(query_date, str):
            query_date = datetime.date.fromisoformat(query_date).date()
        self.logger.info(f"[QUERY] Getting todos for reminder date: {query_date}")
        try:
            with self.db as conn:
                cur = conn.cursor()
                if query_date:
                    date_str = query_date.isoformat()
                    cur.execute(
                        """
                        SELECT 
                            td.todo_id, 
                            t.template_id,
                            t.todo_content, 
                            td.user_id, 
                            td.status, 
                            td.reminder_time, 
                            td.ddl_time
                        FROM todos td
                        JOIN todo_templates t ON td.template_id = t.template_id
                        WHERE DATE(td.reminder_time) = ?
                        ORDER BY td.reminder_time
                        """,
                        (date_str,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 
                            td.todo_id,
                            t.template_id,
                            t.todo_content, 
                            td.user_id, 
                            td.reminder_time,
                            td.ddl_time,
                            td.status,
                            td.created_at,
                            td.updated_at
                        FROM todos td
                        JOIN todo_templates t ON td.template_id = t.template_id
                        ORDER BY td.reminder_time
                        """
                    )

                results = cur.fetchall()
                return results
        except sqlite3.Error as e:
            self.logger.info(f"ERROR querying todos: {e}")
            return []

    def get_todo(self, todo_id: int):
        """get a specific todo by todo_id"""
        try:
            with self.db as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        td.todo_id, 
                        t.todo_content, 
                        td.user_id, 
                        td.reminder_time, 
                        td.ddl_time,
                        td.status,
                        td.created_at,
                        td.updated_at
                    FROM todos td
                    JOIN todo_templates t ON td.template_id = t.template_id
                    WHERE td.todo_id = ?
                    """,
                    (todo_id,),
                )
                result = cur.fetchone()
                return result

        except sqlite3.Error as e:
            self.logger.info(f"ERROR querying todo {todo_id}: {e}")
            return None
