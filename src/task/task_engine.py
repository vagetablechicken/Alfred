from croniter import croniter
import sqlite3
from datetime import datetime, timedelta, date
import logging

from .database.database_manager import DBSession
from utils.config import get_db_path


class TaskEngine:
    def __init__(self, db_file=None):
        if db_file is None:
            db_file = get_db_path()
        self.db_file = db_file
        self.logger = logging.getLogger(__name__)
        # setup database
        assert self._get_db().create_tables()

    def _get_db(self):
        return DBSession(self.db_file)

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

    def _create_todo_transaction(
        self,
        cur,
        user_id,
        template_id,
        ddl_offset,
        reminder_time: datetime,
        create_time: datetime,
    ):
        """
        (内部函数) 在数据库事务中创建 todo 和 log。
        - reminder_time: 任务“应该”提醒的时间 (来自 cron)
        - sim_time: 事务“实际”发生的时间 (现在)
        """
        # 1. 计算 DDL 时间
        ddl_time = reminder_time + self._parse_offset(ddl_offset)

        # 2. 插入 todos 表
        cur.execute(
            """
            INSERT INTO todos (template_id, user_id, status, reminder_time, ddl_time, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                template_id,
                user_id,
                reminder_time.isoformat(),
                ddl_time.isoformat(),
                create_time.isoformat(),
                create_time.isoformat(),
            ),
        )

        todo_id = cur.lastrowid

        # 3. 插入 todo_status_logs 表
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
            with self._get_db() as conn:
                cur = conn.cursor()
                # no matter template create time, check all active templates
                cur.execute(
                    """
                    SELECT user_id, template_id, cron, ddl_offset, todo_content, run_once
                    FROM todo_templates
                    WHERE is_active = 1
                """
                )
                active_templates = cur.fetchall()

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
                        cur.execute(
                            """
                            SELECT 1 FROM todos
                            WHERE user_id = ? AND template_id = ? AND reminder_time = ?
                        """,
                            (user_id, template_id, last_due_time.isoformat()),
                        )

                        if cur.fetchone():
                            continue  # already exists, skip

                        self.logger.info(
                            f"[Scheduler] CREATING: Task for {user_id} ({todo_content}) at {last_due_time}"
                        )
                        with conn:
                            self._create_todo_transaction(
                                cur,
                                user_id,
                                template_id,
                                ddl_offset,
                                reminder_time=last_due_time,
                                create_time=current_time,
                            )
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
                self.logger.info("[Scheduler] No new tasks to schedule at this time.")
            else:
                self.logger.info(f"[Scheduler] Created {created_count} new tasks.")

        except sqlite3.Error as e:
            self.logger.error(f"[Scheduler] DB ERROR: {e}")

    def run_escalator(self, current_time: datetime | str):
        """
        escalator to escalate overdue tasks
        """
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [ESCALATOR] running at {current_time} ---")

        escalated_count = 0
        try:
            with self._get_db() as conn:
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT todo_id FROM todos
                    WHERE status = 'pending' AND ddl_time < ?
                """,
                    (current_time.isoformat(),),
                )

                tasks_to_escalate = cur.fetchall()

                if not tasks_to_escalate:
                    self.logger.info("[Escalator] No tasks to escalate.")
                    return

                for (todo_id,) in tasks_to_escalate:
                    try:
                        with conn:
                            # update todos table
                            cur.execute(
                                """
                                UPDATE todos SET status = 'escalated', updated_at = ?
                                WHERE todo_id = ? AND status = 'pending'
                            """,
                                (current_time.isoformat(), todo_id),
                            )

                            # insert into todo_status_logs table
                            cur.execute(
                                """
                                INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
                                VALUES (?, 'pending', 'escalated', ?)
                            """,
                                (todo_id, current_time.isoformat()),
                            )

                        self.logger.info(f"[Escalator] ESCALATED Todo {todo_id}")
                        escalated_count += 1
                    except sqlite3.Error as e:
                        self.logger.error(
                            f"[Escalator] ERROR escalating Todo {todo_id}: {e}"
                        )

            self.logger.info(f"[Escalator] Escalated {escalated_count} tasks.")

        except sqlite3.Error as e:
            self.logger.error(f"[Escalator] DB ERROR: {e}")

