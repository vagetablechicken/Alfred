from croniter import croniter
import datetime
import sqlite3
from datetime import timedelta
import logging

from .database.database_manager import DatabaseManager


class TaskEngine:
    def __init__(self, db_manager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)

    def _parse_bias(self, bias_str: str) -> timedelta:
        """简单的 ddl_bias 解析器 (例如 '1h', '30m', '2d')"""
        # (为了演示简洁性，我们只实现 'h' 和 'm')
        if bias_str.endswith("h"):
            return timedelta(hours=int(bias_str[:-1]))
        elif bias_str.endswith("m"):
            return timedelta(minutes=int(bias_str[:-1]))
        else:
            raise ValueError(f"Unknown bias format: {bias_str}")

    def _create_todo_transaction(
        self,
        cur,
        user_id,
        template_id,
        ddl_bias,
        reminder_time: datetime.datetime,
        sim_time: datetime.datetime,
    ):
        """
        (内部函数) 在数据库事务中创建 todo 和 log。
        - reminder_time: 任务“应该”提醒的时间 (来自 cron)
        - sim_time: 事务“实际”发生的时间 (现在)
        """
        # 1. 计算 DDL 时间
        ddl_time = reminder_time + self._parse_bias(ddl_bias)

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
                sim_time.isoformat(),
                sim_time.isoformat(),
            ),
        )

        todo_id = cur.lastrowid

        # 3. 插入 todo_status_logs 表
        cur.execute(
            """
            INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
            VALUES (?, NULL, 'pending', ?)
            """,
            (todo_id, sim_time.isoformat()),
        )
        return todo_id

    def run_scheduler(self, current_time: datetime.datetime):
        """
        (幂等调度器)
        运行调度器，为所有“上一个应执行”但尚未创建的任务创建实例。
        """
        self.logger.info(f"\n--- [SCHEDULER] running at {current_time} ---")

        created_count = 0
        try:
            with self.db as conn:
                cur = conn.cursor()

                # 1. 直接查询 task_templates
                cur.execute(
                    """
                    SELECT user_id, template_id, cron, ddl_bias, task_name, run_once
                    FROM task_templates
                    WHERE is_active = 1
                """
                )
                active_templates = cur.fetchall()

                for (
                    user_id,
                    template_id,
                    cron,
                    ddl_bias,
                    task_name,
                    run_once,
                ) in active_templates:
                    try:
                        # 2. 获取“上一个”应执行的时间点
                        cron_iter = croniter(cron, current_time)
                        last_due_time = cron_iter.get_prev(datetime.datetime)

                        # 3. “判断”是否已存在
                        cur.execute(
                            """
                            SELECT 1 FROM todos
                            WHERE user_id = ? AND template_id = ? AND reminder_time = ?
                        """,
                            (user_id, template_id, last_due_time.isoformat()),
                        )

                        if cur.fetchone():
                            continue  # 已存在, 跳过

                        # 4. 不存在, 在事务中创建
                        self.logger.info(
                            f"[Scheduler] CREATING: Task for {user_id} ({task_name}) at {last_due_time}"
                        )
                        with conn:  # 使用 'with conn' 自动管理 commit/rollback
                            self._create_todo_transaction(
                                cur,
                                user_id,
                                template_id,
                                ddl_bias,
                                reminder_time=last_due_time,
                                sim_time=current_time,
                            )
                        created_count += 1
                        if run_once:
                            # 如果是“只运行一次”，则禁用模板，之后再设置is_active=1的话，还可以再进行“只运行一次”
                            self.logger.info(
                                f"[Scheduler] Disabling one-time template {template_id} for {user_id}"
                            )
                            cur.execute(
                                """
                                UPDATE task_templates SET is_active = 0 WHERE template_id = ?
                            """,
                                (template_id,),
                            )

                    except Exception as e:
                        self.logger.error(
                            f"[Scheduler] ERROR processing {user_id} / {task_name}: {e}"
                        )

            if created_count == 0:
                self.logger.info("[Scheduler] No new tasks to schedule at this time.")
            else:
                self.logger.info(f"[Scheduler] Created {created_count} new tasks.")

        except sqlite3.Error as e:
            self.logger.error(f"[Scheduler] DB ERROR: {e}")

    def run_escalation(self, simulation_time: datetime.datetime):
        """
        (升级器)
        检查并升级已过期的 'pending' 任务
        """
        self.logger.info(f"\n--- [ESCALATOR] running at {simulation_time} ---")

        escalated_count = 0
        try:
            with self.db as conn:
                cur = conn.cursor()
                # 1. 查找所有状态为 'pending' 且已过 ddl_time 的任务
                cur.execute(
                    """
                    SELECT id FROM todos
                    WHERE status = 'pending' AND ddl_time < ?
                """,
                    (simulation_time.isoformat(),),
                )

                tasks_to_escalate = cur.fetchall()

                if not tasks_to_escalate:
                    self.logger.info("[Escalator] No tasks to escalate.")
                    return

                for (todo_id,) in tasks_to_escalate:
                    # 2. 在事务中更新
                    try:
                        with conn:
                            # (a) 更新 todos 表
                            cur.execute(
                                """
                                UPDATE todos SET status = 'escalated', updated_at = ?
                                WHERE id = ? AND status = 'pending'
                            """,
                                (simulation_time.isoformat(), todo_id),
                            )

                            # (b) 插入 logs 表
                            cur.execute(
                                """
                                INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
                                VALUES (?, 'pending', 'escalated', ?)
                            """,
                                (todo_id, simulation_time.isoformat()),
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

    def complete_task(self, todo_id: int, sim_time: datetime.datetime):
        """(用户操作) 完成任务"""
        self.logger.info(f"\n--- [USER] Completing Todo {todo_id} at {sim_time} ---")
        try:
            with self.db as conn:
                with conn:  # 自动事务
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM todos WHERE id = ?", (todo_id,))
                    result = cur.fetchone()

                    if not result:
                        self.logger.error(f"ERROR: Todo {todo_id} not found.")
                        return

                    old_status = result[0]
                    if old_status in ("completed", "revoked"):
                        self.logger.info(
                            f"Todo {todo_id} is already in a final state ({old_status})."
                        )
                        return

                    cur.execute(
                        "UPDATE todos SET status = 'completed', updated_at = ? WHERE id = ?",
                        (sim_time.isoformat(), todo_id),
                    )
                    cur.execute(
                        "INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, ?, 'completed', ?)",
                        (todo_id, old_status, sim_time.isoformat()),
                    )
                self.logger.info(f"COMPLETED Todo {todo_id} (was {old_status})")
        except sqlite3.Error as e:
            self.logger.error(f"ERROR completing Todo {todo_id}: {e}")

    def revert_task_completion(self, todo_id: int, sim_time: datetime.datetime):
        """(用户操作) 撤销完成 (错点了)"""
        self.logger.info(f"\n--- [USER] Reverting Todo {todo_id} at {sim_time} ---")
        try:
            with self.db as conn:
                with conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT status, ddl_time FROM todos WHERE id = ?", (todo_id,)
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

                    # 关键逻辑：决定退回哪个状态
                    ddl_time = datetime.datetime.fromisoformat(ddl_time_str)
                    new_status = "escalated" if sim_time >= ddl_time else "pending"

                    cur.execute(
                        "UPDATE todos SET status = ?, updated_at = ? WHERE id = ?",
                        (new_status, sim_time.isoformat(), todo_id),
                    )
                    cur.execute(
                        "INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at) VALUES (?, 'completed', ?, ?)",
                        (todo_id, new_status, sim_time.isoformat()),
                    )
                self.logger.info(
                    f"REVERTED Todo {todo_id} from 'completed' back to '{new_status}'"
                )
        except sqlite3.Error as e:
            self.logger.error(f"ERROR reverting Todo {todo_id}: {e}")

    def set_template_active_status(
        self, template_id: int, is_active: bool, sim_time: datetime.datetime
    ):
        """(管理员操作) 禁用或启用模板，并作废相关任务"""
        status_str = "Activating" if is_active else "Deactivating"
        self.logger.info(
            f"\n--- [ADMIN] {status_str} Template {template_id} at {sim_time} ---"
        )

        try:
            with self.db as conn:
                with conn:  # 自动事务
                    cur = conn.cursor()

                    # 1. 更新模板本身
                    cur.execute(
                        "UPDATE task_templates SET is_active = ? WHERE template_id = ?",
                        (1 if is_active else 0, template_id),
                    )

                    tasks_to_revoke = []
                    # 2. (核心) 如果是“禁用”，则 Revoke 所有未完成的任务
                    if not is_active:
                        # 查找所有这个模板的 'pending' 或 'escalated' 任务
                        cur.execute(
                            """
                            SELECT id, status FROM todos 
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
                            # (a) 更新 todos
                            cur.execute(
                                """
                                UPDATE todos SET status = 'revoked', updated_at = ?
                                WHERE id = ?
                            """,
                                (sim_time.isoformat(), todo_id),
                            )

                            # (b) 插入 logs (现在我们有 old_status 了)
                            cur.execute(
                                """
                                INSERT INTO todo_status_logs (todo_id, old_status, new_status, changed_at)
                                VALUES (?, ?, 'revoked', ?)
                            """,
                                (todo_id, old_status, sim_time.isoformat()),
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

    # --- 辅助函数 ---
    def add_template(self, user_id, name, cron, bias, run_once=0):
        self.logger.info(f"\nAdding template for {user_id}: {name}")
        with self.db as conn:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO task_templates (user_id, task_name, cron, ddl_bias, run_once) VALUES (?, ?, ?, ?, ?)",
                    (user_id, name, cron, bias, run_once),
                )
                return cur.lastrowid  # 返回 template_id

    def print_table_status(self):
        """辅助函数：打印当前所有状态"""
        print("\n" + "=" * 50)
        print("CURRENT TABLE STATUS")
        print("=" * 50)
        try:
            with self.db as conn:
                cur = conn.cursor()

                print("\n--- Todos (Current Status) ---")
                cur.execute(
                    "SELECT id, user_id, template_id, status, reminder_time, ddl_time FROM todos ORDER BY id"
                )
                rows = cur.fetchall()
                if not rows:
                    print("Empty")
                for row in rows:
                    print(row)

                print("\n--- Todo Status Logs (History) ---")
                cur.execute(
                    "SELECT log_id, todo_id, old_status, new_status, changed_at FROM todo_status_logs ORDER BY todo_id, log_id"
                )
                rows = cur.fetchall()
                if not rows:
                    print("Empty")
                for row in rows:
                    print(row)
            print("=" * 50 + "\n")
        except sqlite3.Error as e:
            print(f"ERROR printing status: {e}")

    def get_todos(self, query_date: datetime.date):
        """辅助函数：获取指定日期的 todos"""
        print(f"\n--- [QUERY] Getting todos for reminder date: {query_date} ---")
        try:
            with self.db as conn:
                cur = conn.cursor()

                # 1. JOIN task_templates 以获取 task_name
                # 2. 使用 DATE(td.reminder_time) 来匹配 YYYY-MM-DD
                # 3. Python 的 'datetime.date' 对象 (query_date)
                #    会被 sqlite3 库自动转换为 'YYYY-MM-DD' 字符串用于查询。
                cur.execute(
                    """
                    SELECT 
                        td.id, 
                        t.task_name, 
                        td.user_id, 
                        td.status, 
                        td.reminder_time, 
                        td.ddl_time
                    FROM todos td
                    JOIN task_templates t ON td.template_id = t.template_id
                    WHERE DATE(td.reminder_time) = ?
                    ORDER BY td.user_id, td.reminder_time
                    """,
                    (query_date,),
                )

                results = cur.fetchall()
                print(f"Found {len(results)} todos for {query_date}.")
                return results

        except sqlite3.Error as e:
            print(f"ERROR querying todos: {e}")
            return []

    def get_todo(self, todo_id: int):
        """辅助函数：获取单个 todo 详情"""
        try:
            with self.db as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT 
                        td.id, 
                        t.task_name, 
                        td.user_id, 
                        td.status, 
                        td.reminder_time, 
                        td.ddl_time
                    FROM todos td
                    JOIN task_templates t ON td.template_id = t.template_id
                    WHERE td.id = ?
                    """,
                    (todo_id,),
                )
                result = cur.fetchone()
                return result

        except sqlite3.Error as e:
            print(f"ERROR querying todo {todo_id}: {e}")
            return None


# 全局引擎实例
db_manager = DatabaseManager("tasks.db")
task_engine = TaskEngine(db_manager)
