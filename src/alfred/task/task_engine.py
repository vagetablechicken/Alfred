from croniter import croniter
import sqlite3
from datetime import datetime, timedelta
import logging

from .vault import LockedSqliteVault


class TaskEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.vault = LockedSqliteVault()

    def _parse_offset(self, offset_str: str) -> timedelta:
        """handle simple ddl_offset like '5m', '2h', '1d' etc."""
        unit = offset_str[-1]
        value = int(offset_str[:-1])
        if unit == "s":
            # not recommended, but support for completeness and testing
            return timedelta(seconds=value)
        elif unit == "m":
            return timedelta(minutes=value)
        elif unit == "h":
            return timedelta(hours=value)
        elif unit == "d":
            return timedelta(days=value)
        else:
            raise ValueError(f"Unsupported offset unit: {unit}")

    def _create_todo(
        self,
        cur,
        user_id,
        template_id,
        ddl_offset,
        remind_time: datetime,
        create_time: datetime,
    ):
        # 1. 计算 DDL 时间
        ddl_time = remind_time + self._parse_offset(ddl_offset)

        # 2. 插入 todos 表
        cur.execute(
            """
            INSERT INTO todos (template_id, user_id, status, remind_time, ddl_time, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                template_id,
                user_id,
                remind_time.isoformat(),
                ddl_time.isoformat(),
                create_time.isoformat(),
                create_time.isoformat(),
            ),
        )
        todo_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
            VALUES (?, NULL, 'pending', ?)
            """,
            (todo_id, create_time.isoformat()),
        )
        return todo_id

    def run_scheduler(self, current_time: datetime | str):
        """
        scheduler to create todos based on active templates
        """
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [SCHEDULER] running at {current_time} ---")

        created_count = 0
        try:
            with self.vault.transaction() as cur:
                # no matter template create time, check all active templates
                active_templates = cur.execute(
                    """
                    SELECT user_id, template_id, cron, ddl_offset, todo_content, run_once
                    FROM todo_templates
                    WHERE is_active = 1
                """
                ).fetchall()

                for (
                    user_id,
                    template_id,
                    cron,
                    ddl_offset,
                    todo_content,
                    run_once,
                ) in active_templates:
                    try:
                        # use croniter to find the last due time before current_time
                        cron_iter = croniter(cron, current_time)
                        last_due_time = cron_iter.get_prev(datetime)
                        # check if a todo already exists for this user/template/time
                        if cur.execute(
                            """
                            SELECT 1 FROM todos
                            WHERE user_id = ? AND template_id = ? AND remind_time = ?
                        """,
                            (user_id, template_id, last_due_time.isoformat()),
                        ).fetchone():
                            continue  # already exists, skip

                        self.logger.info(
                            f"[Scheduler] CREATING: Task for {user_id} ({todo_content}) at {last_due_time}"
                        )

                        todo_id = self._create_todo(
                            cur,
                            user_id,
                            template_id,
                            ddl_offset,
                            remind_time=last_due_time,
                            create_time=current_time,
                        )
                        self.logger.info(f"[Scheduler] Created todo ID {todo_id} for user {user_id}")
                        created_count += 1
                        if run_once:
                            # if run_once, disable the template after creating the task
                            self.logger.info(
                                f"[Scheduler] Disabling one-time template {template_id} for {user_id}"
                            )
                            cur.execute(
                                """
                                UPDATE todo_templates SET is_active = 0 WHERE template_id = ?
                            """,
                                (template_id,),
                            )

                    except Exception as e:
                        self.logger.error(
                            f"[Scheduler] ERROR processing {user_id} / {todo_content}: {e}"
                        )

            if created_count == 0:
                self.logger.info("[Scheduler] No new todo to schedule at this time.")
            else:
                self.logger.info(f"[Scheduler] Created {created_count} new todo.")

        except sqlite3.Error as e:
            self.logger.error(f"[Scheduler] DB ERROR: {e}")


instance = TaskEngine()
