-- cron 任务模板表
CREATE TABLE IF NOT EXISTS todo_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    todo_content TEXT NOT NULL,
    user_id TEXT NOT NULL,
    cron TEXT NOT NULL,                           -- '0 9 * * *'
    ddl_offset TEXT NOT NULL,                     -- '1h'
    -- 1 = 运行一次后自动禁用, 0 = 周期性运行
    run_once INTEGER DEFAULT 0 NOT NULL,
    is_active INTEGER DEFAULT 1 NOT NULL,        -- 1 = 激活, 0 = 禁用
    created_at TEXT DEFAULT (DATETIME('now', 'localtime'))
);

-- 任务实例表
CREATE TABLE IF NOT EXISTS todos (
    todo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    reminder_time TEXT NOT NULL,
    ddl_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL 
        CHECK(status IN ('pending', 'completed', 'revoked', 'escalated')), 
    created_at TEXT DEFAULT (DATETIME('now', 'localtime')),
    updated_at TEXT DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY(template_id) REFERENCES todo_templates(template_id)
);

-- 状态日志表
CREATE TABLE IF NOT EXISTS todo_status_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    todo_id INTEGER NOT NULL,
    old_status TEXT 
        CHECK(old_status IN ('pending', 'completed', 'revoked', 'escalated')),
    new_status TEXT NOT NULL 
        CHECK(new_status IN ('pending', 'completed', 'revoked', 'escalated')),
    changed_at TEXT DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY(todo_id) REFERENCES todos(todo_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_todos_user_status 
ON todos(user_id, status);

CREATE INDEX IF NOT EXISTS idx_todos_status_ddl 
ON todos(status, ddl_time);

CREATE INDEX IF NOT EXISTS idx_logs_todo_id 
ON todo_status_logs(todo_id);

CREATE INDEX IF NOT EXISTS idx_templates_user_active
ON todo_templates(user_id, is_active);
