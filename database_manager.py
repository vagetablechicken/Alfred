import sqlite3
import datetime
from datetime import timedelta
from croniter import croniter
import os
import sys


# ------------------------------------------------------------------
# 1. 数据库管理类 (从 init.sql 读取)
# ------------------------------------------------------------------
class DatabaseManager:
    """
    一个简单的 SQLite 数据库连接和操作封装。
    - 自动处理连接的打开/关闭。
    - 自动启用外键 (PRAGMA foreign_keys = ON)。
    """

    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file)
        # 关键: 必须在每次连接时都执行
        self.conn.execute("PRAGMA foreign_keys = ON;")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def create_tables(self, init_sql_file="init.sql"):
        """
        执行初始化 SQL 脚本来创建所有表。
        假设 'init.sql' 脚本中不包含 'COMMIT;'。
        """
        print(f"Initializing database tables from '{init_sql_file}'...")
        try:
            with open(init_sql_file, "r", encoding="utf-8") as f:
                sql_script = f.read()

            # (1) 使用 __enter__ 获取连接 (已开启 foreign_keys)
            with self as conn:
                # (2) executescript 会自动处理 DDL 事务
                conn.executescript(sql_script)

            print("Database and tables initialized successfully.")
            return True

        except FileNotFoundError:
            print(f"ERROR: '{init_sql_file}' not found. Tables were not created.")
            return False
        except sqlite3.Error as e:
            print(f"ERROR during table initialization: {e}")
            return False


# ------------------------------------------------------------------
# 2. 核心业务逻辑引擎 (与上一版相同)
# ------------------------------------------------------------------
class TaskEngine:
    def __init__(self, db_manager):
        self.db = db_manager

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

    def run_scheduler(self, simulation_time: datetime.datetime):
        """
        (幂等调度器)
        运行调度器，为所有“上一个应执行”但尚未创建的任务创建实例。
        """
        print(f"\n--- [SCHEDULER] running at {simulation_time} ---")

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
                        cron_iter = croniter(cron, simulation_time)
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
                        print(
                            f"[Scheduler] CREATING: Task for {user_id} ({task_name}) at {last_due_time}"
                        )
                        with conn:  # 使用 'with conn' 自动管理 commit/rollback
                            self._create_todo_transaction(
                                cur,
                                user_id,
                                template_id,
                                ddl_bias,
                                reminder_time=last_due_time,
                                sim_time=simulation_time,
                            )
                        created_count += 1
                        if run_once:
                            # 如果是“只运行一次”，则禁用模板，之后再设置is_active=1的话，还可以再进行“只运行一次”
                            print(
                                f"[Scheduler] Disabling one-time template {template_id} for {user_id}"
                            )
                            cur.execute(
                                """
                                UPDATE task_templates SET is_active = 0 WHERE template_id = ?
                            """,
                                (template_id,),
                            )

                    except Exception as e:
                        print(
                            f"[Scheduler] ERROR processing {user_id} / {task_name}: {e}"
                        )

            if created_count == 0:
                print("[Scheduler] No new tasks to schedule at this time.")
            else:
                print(f"[Scheduler] Created {created_count} new tasks.")

        except sqlite3.Error as e:
            print(f"[Scheduler] DB ERROR: {e}")

    def run_escalation(self, simulation_time: datetime.datetime):
        """
        (升级器)
        检查并升级已过期的 'pending' 任务
        """
        print(f"\n--- [ESCALATOR] running at {simulation_time} ---")

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
                    print("[Escalator] No tasks to escalate.")
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

                        print(f"[Escalator] ESCALATED Todo {todo_id}")
                        escalated_count += 1
                    except sqlite3.Error as e:
                        print(f"[Escalator] ERROR escalating Todo {todo_id}: {e}")

            print(f"[Escalator] Escalated {escalated_count} tasks.")

        except sqlite3.Error as e:
            print(f"[Escalator] DB ERROR: {e}")

    def complete_task(self, todo_id: int, sim_time: datetime.datetime):
        """(用户操作) 完成任务"""
        print(f"\n--- [USER] Completing Todo {todo_id} at {sim_time} ---")
        try:
            with self.db as conn:
                with conn:  # 自动事务
                    cur = conn.cursor()
                    cur.execute("SELECT status FROM todos WHERE id = ?", (todo_id,))
                    result = cur.fetchone()

                    if not result:
                        print(f"ERROR: Todo {todo_id} not found.")
                        return

                    old_status = result[0]
                    if old_status in ("completed", "revoked"):
                        print(
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
                print(f"COMPLETED Todo {todo_id} (was {old_status})")
        except sqlite3.Error as e:
            print(f"ERROR completing Todo {todo_id}: {e}")

    def revert_task_completion(self, todo_id: int, sim_time: datetime.datetime):
        """(用户操作) 撤销完成 (错点了)"""
        print(f"\n--- [USER] Reverting Todo {todo_id} at {sim_time} ---")
        try:
            with self.db as conn:
                with conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT status, ddl_time FROM todos WHERE id = ?", (todo_id,)
                    )
                    result = cur.fetchone()

                    if not result:
                        print(f"ERROR: Todo {todo_id} not found.")
                        return
                    old_status, ddl_time_str = result

                    if old_status != "completed":
                        print(
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
                print(
                    f"REVERTED Todo {todo_id} from 'completed' back to '{new_status}'"
                )
        except sqlite3.Error as e:
            print(f"ERROR reverting Todo {todo_id}: {e}")

    def set_template_active_status(
        self, template_id: int, is_active: bool, sim_time: datetime.datetime
    ):
        """(管理员操作) 禁用或启用模板，并作废相关任务"""
        status_str = "Activating" if is_active else "Deactivating"
        print(f"\n--- [ADMIN] {status_str} Template {template_id} at {sim_time} ---")

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
                            print("No active todos to revoke.")

                        for todo_id, old_status in tasks_to_revoke:
                            print(f"REVOKING Todo {todo_id} (was {old_status})...")
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

                print(
                    f"Successfully set Template {template_id} active status to {is_active}"
                )
                if not is_active and tasks_to_revoke:
                    print(f"Revoked {len(tasks_to_revoke)} associated tasks.")

        except sqlite3.Error as e:
            print(f"ERROR changing template status: {e}")

    # --- 辅助函数 ---
    def add_template(self, user_id, name, cron, bias, run_once=0):
        print(f"\nAdding template for {user_id}: {name}")
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


# ------------------------------------------------------------------
# 3. 运行演示
# ------------------------------------------------------------------
if __name__ == "__main__":

    DB_FILE = "tasks_demo.db"
    INIT_FILE = "init.sql"

    # --- 1. (重置) ---
    if not os.path.exists(INIT_FILE):
        print(f"ERROR: '{INIT_FILE}' not found. Please create it first.")
        print("This script will now exit.")
        sys.exit(1)  # 退出脚本

    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old {DB_FILE}")

    # --- 2. 初始化 ---
    dbm = DatabaseManager(DB_FILE)
    engine = TaskEngine(dbm)

    # create_tables 会读取 init.sql
    if not dbm.create_tables(init_sql_file=INIT_FILE):
        print("Failed to initialize database. Exiting.")
        sys.exit(1)

    # --- 3. 创建模板 (计划) ---
    # (为了演示，我们使用每分钟的 cron)
    # 真实世界中, cron 应该是 "0 9 * * *"

    # Alice: 每分钟提醒, 5分钟后过期
    template_alice_id = engine.add_template("Alice", "每分钟打卡", "* * * * *", "5m")
    # Bob: 每分钟提醒, 2分钟后过期
    template_bob_id = engine.add_template("Bob", "每分钟喝水", "* * * * *", "2m")

    engine.print_table_status()

    # --- 4. 模拟时间流逝 ---

    # T=1. 模拟 10:00:05 (调度器运行)
    sim_time = datetime.datetime(2025, 11, 8, 10, 0, 5)
    # croniter(* * * * *).get_prev(10:00:05) -> 10:00:00
    engine.run_scheduler(sim_time)
    # 应该为 Alice 和 Bob 创建 10:00:00 的任务 (ID 1, 2)
    engine.print_table_status()

    # T=2. 模拟 10:01:05 (调度器再次运行 - 幂等性测试)
    engine.run_scheduler(sim_time)
    # (注意：传入了和 T=1 相同的时间)
    # (幂等性测试：不应该创建重复任务)
    print("\n--- Running scheduler AGAIN at same time (idempotency test) ---")
    engine.run_scheduler(sim_time)

    # T=3. 模拟 10:01:05 (调度器在新的一分钟运行)
    sim_time = datetime.datetime(2025, 11, 8, 10, 1, 5)
    engine.run_scheduler(sim_time)
    # 应该为 Alice 和 Bob 创建 10:01:00 的任务 (ID 3, 4)
    engine.print_table_status()

    # T=4. 模拟 10:01:10 (Alice 完成了 T=1 的任务)
    sim_time = datetime.datetime(2025, 11, 8, 10, 1, 10)
    engine.complete_task(todo_id=1, sim_time=sim_time)  # ID=1 (Alice@10:00)

    # T=5. 模拟 10:03:00 (升级器运行)
    # Bob@10:00 的任务 (ID=2) DDL 是 10:02:00, 应该被升级
    # Bob@10:01 的任务 (ID=4) DDL 是 10:03:00, (<=) 暂时不升级
    sim_time = datetime.datetime(2025, 11, 8, 10, 3, 0)
    engine.run_escalation(sim_time)
    engine.print_table_status()  # ID=2 变为 'escalated'

    # T=6. 模拟 10:03:10 (Alice “错点”了 T=3 的任务)
    sim_time = datetime.datetime(2025, 11, 8, 10, 3, 10)
    engine.revert_task_completion(todo_id=3, sim_time=sim_time)  # ID=3 (Alice@10:01)
    # ID=3 的 DDL 是 10:06:00。
    # 10:03:10 < 10:06:00, 所以应退回 'pending'
    engine.print_table_status()  # ID=3 变为 'pending'

    # T=7. 模拟 10:03:20 (Alice 又“错点”了 T=1 的任务)
    sim_time = datetime.datetime(2025, 11, 8, 10, 3, 20)
    engine.revert_task_completion(todo_id=1, sim_time=sim_time)  # ID=1 (Alice@10:00)
    # ID=1 的 DDL 是 10:05:00。
    # 10:03:20 < 10:05:00, 所以应退回 'pending'
    engine.print_table_status()  # ID=1 变为 'pending'

    # T=8. 模拟 10:03:30 (管理员禁用了 Bob 的模板)
    sim_time = datetime.datetime(2025, 11, 8, 10, 3, 30)
    engine.set_template_active_status(
        template_id=template_bob_id, is_active=False, sim_time=sim_time
    )
    # 应该把 Bob 的 ID=2 ('escalated') 和 ID=4 ('pending') 都设为 'revoked'
    engine.print_table_status()

    # T=9. 模拟 10:04:05 (调度器再次运行)
    sim_time = datetime.datetime(2025, 11, 8, 10, 4, 5)
    # croniter(* * * * *).get_prev(10:04:05) -> 10:04:00
    engine.run_scheduler(sim_time)
    # 此时, Bob 的模板是 is_active=0
    # 应该只为 Alice 创建 10:04:00 的任务 (ID=5)
    engine.print_table_status()
