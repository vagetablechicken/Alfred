from datetime import datetime, date
import logging
import sqlite3

from alfred.task.vault import LockedSqliteVault  # import the singleton vault instance


class Bulletin:
    """
    Read raw meta data from singleton vault instance. Manage templates and todos.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.vault = LockedSqliteVault()

    def complete_todo(self, todo_id: int, current_time: datetime | str):
        """User completes a todo"""
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Completing Todo {todo_id} at {current_time} ---")
        try:
            with self.vault.transaction() as cur:
                result = cur.execute(
                    "SELECT status FROM todos WHERE todo_id = ?", (todo_id,)
                ).fetchall()
                assert (
                    len(result) == 1
                ), f"Expected one result for todo_id {todo_id}, got {len(result)}"
                old_status = result[0]["status"]
                if old_status in ("completed", "revoked"):
                    self.logger.info(
                        f"Todo {todo_id} is already in a final state ({old_status})."
                    )
                    return

                cur.execute(
                    "UPDATE todos SET status = 'completed', updated_at = ? WHERE todo_id = ?",
                    (current_time.isoformat(), todo_id),
                )
                cur.execute(
                    "INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, ?, 'completed', ?)",
                    (todo_id, old_status, current_time.isoformat()),
                )
            self.logger.info(f"COMPLETED Todo {todo_id} (was {old_status})")
        except sqlite3.Error as e:
            self.logger.error(f"ERROR completing Todo {todo_id}: {e}")

    def revert_todo_completion(self, todo_id: int, current_time: datetime | str):
        """user reverts a completed task back to pending/escalated"""
        if isinstance(current_time, str):
            current_time = datetime.datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Reverting Todo {todo_id} at {current_time} ---")
        try:
            with self.vault.transaction() as cur:
                result = cur.execute(
                    "SELECT status FROM todos WHERE todo_id = ?", (todo_id,)
                ).fetchall()

                if not result:
                    self.logger.error(f"ERROR: Todo {todo_id} not found.")
                    return
                assert (
                    len(result) == 1
                ), f"Expected one result for todo_id {todo_id}, got {len(result)}"

                old_status = result[0]["status"]

                if old_status != "completed":
                    self.logger.error(
                        f"ERROR: Todo {todo_id} is not 'completed'. Cannot revert."
                    )
                    return

                # we don't determine new status based on ddl_time, all go back to pending
                new_status = "pending"

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
        self, template_id: int, is_active: bool, current_time: datetime | str
    ):
        """admin activates/deactivates a template"""
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        status_str = "Activating" if is_active else "Deactivating"
        self.logger.info(
            f"--- [ADMIN] {status_str} Template {template_id} at {current_time} ---"
        )

        try:
            with self.vault.transaction() as cur:
                # update template active status
                cur.execute(
                    "UPDATE todo_templates SET is_active = ? WHERE template_id = ?",
                    (1 if is_active else 0, template_id),
                )

                tasks_to_revoke = []

                if not is_active:
                    # if deactivating, revoke all pending/escalated tasks from this template
                    tasks_to_revoke = cur.execute(
                        """
                        SELECT todo_id, status FROM todos 
                        WHERE template_id = ? AND status IN ('pending', 'escalated')
                    """,
                        (template_id,),
                    ).fetchall()

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
        with self.vault.transaction() as cur:
            cur.execute(
                "INSERT INTO todo_templates (user_id, todo_content, cron, ddl_offset, run_once) VALUES (?, ?, ?, ?, ?)",
                (user_id, todo_content, cron, ddl_offset, run_once),
            )
            template_id = cur.lastrowid
            self.logger.info(f"Added template {template_id} for {user_id}")
        return template_id

    def fetch_all(self):
        """
        Return dictionary of all tables and their rows.
        """
        self.logger.info(f"[QUERY] Fetching all data from all tables")
        all_data = {}
        with self.vault.transaction() as cur:
            # get list of tables
            tables = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for table in tables:
                table_name = table["name"]
                rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
                all_data[table_name] = [dict(row) for row in rows]
        return all_data

    def get_templates(self):
        """get all todo templates"""
        self.logger.info(f"[QUERY] Getting all todo templates")
        with self.vault.transaction() as cur:
            return cur.execute(
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
            ).fetchall()

    def get_todos(self, query_date: date | str = None):
        """get todos for a specific date (YYYY-MM-DD) or all if None"""
        if query_date and isinstance(query_date, str):
            query_date = date.fromisoformat(query_date).date()
        self.logger.info(f"[QUERY] Getting todos for reminder date: {query_date}")
        with self.vault.transaction() as cur:
            if query_date:
                return cur.execute(
                    """
                            SELECT 
                                td.todo_id, 
                                t.template_id,
                                t.todo_content, 
                                td.user_id, 
                                td.status, 
                                td.remind_time, 
                                td.ddl_time
                            FROM todos td
                            JOIN todo_templates t ON td.template_id = t.template_id
                            WHERE DATE(td.remind_time) = ?
                            ORDER BY td.remind_time
                            """,
                    (query_date.isoformat(),),
                ).fetchall()
            else:
                return cur.execute(
                    """
                            SELECT 
                                td.todo_id,
                                t.template_id,
                                t.todo_content, 
                                td.user_id,
                                td.remind_time,
                                td.ddl_time,
                                td.status,
                                td.created_at,
                                td.updated_at
                            FROM todos td
                            JOIN todo_templates t ON td.template_id = t.template_id
                            ORDER BY td.remind_time
                            """
                ).fetchall()

    def get_todo(self, todo_id: int):
        """get a specific todo by todo_id"""
        self.logger.info(f"[QUERY] Getting Todo {todo_id}")
        with self.vault.transaction() as cur:
            return cur.execute(
                """
                        SELECT 
                            td.todo_id, 
                            t.todo_content, 
                            td.user_id, 
                            td.remind_time, 
                            td.ddl_time,
                            td.status,
                            td.created_at,
                            td.updated_at
                        FROM todos td
                        JOIN todo_templates t ON td.template_id = t.template_id
                        WHERE td.todo_id = ?
                        """,
                (todo_id,),
            ).fetchone()

    def get_todo_log(self, todo_id: int):
        """get the status change log for a specific todo"""
        self.logger.info(f"[QUERY] Getting status log for Todo {todo_id}")
        with self.vault.transaction() as cur:
            return cur.execute(
                """
                    SELECT 
                        log_id,
                        todo_id,
                    old_status,
                    new_status,
                    changed_at
                FROM todo_status_logs
                WHERE todo_id = ?
                ORDER BY changed_at
            """,
                (todo_id,),
            ).fetchall()
