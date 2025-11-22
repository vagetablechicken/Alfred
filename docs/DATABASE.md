# 数据库表结构设计

Alfred 使用 SQLAlchemy ORM 管理数据库，支持 SQLite（开发/测试）和 PostgreSQL（生产）。

## Postgres额外配置

先启动postgres，创建alfred用户和alfred数据库（测试创建alfred_test数据库）。
```bash
docker run --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:latest
docker exec -it postgres psql -U postgres

# 创建用户和数据库
CREATE USER alfred WITH PASSWORD 'alfred';
CREATE DATABASE alfred OWNER alfred;
CREATE DATABASE alfred_test OWNER alfred;
```

## 表概览

系统包含三张核心表：

1. **todo_templates** - 任务模板表（定时任务配置）
2. **todos** - 任务实例表（具体的待办事项）
3. **todo_status_logs** - 状态变更日志表（审计跟踪）

## 表结构详情

### 1. todo_templates（任务模板）

存储周期性任务的配置信息。

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| template_id | INTEGER | 模板ID | PRIMARY KEY, AUTO_INCREMENT |
| todo_content | TEXT | 任务内容 | NOT NULL |
| user_id | VARCHAR(100) | 用户ID | NOT NULL |
| cron | VARCHAR(100) | Cron表达式 | NOT NULL |
| ddl_offset | VARCHAR(50) | 截止时间偏移量（如 "1h", "2d"） | NOT NULL |
| run_once | BOOLEAN | 是否只运行一次 | DEFAULT FALSE |
| is_active | BOOLEAN | 是否启用 | DEFAULT TRUE |
| created_at | TIMESTAMP | 创建时间 | DEFAULT NOW() |

**索引**:
- `idx_templates_user_active` ON (user_id, is_active)

**示例数据**:
```python
template = TodoTemplate(
    user_id="U123456",
    content="每日站会",
    cron="0 9 * * 1-5",  # 工作日早上9点
    ddl_offset="30m",    # 提醒后30分钟截止
    run_once=False,
    is_active=True
)
```

### 2. todos（任务实例）

由模板生成的具体任务实例。

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| todo_id | INTEGER | 任务ID | PRIMARY KEY, AUTO_INCREMENT |
| template_id | INTEGER | 所属模板ID | FOREIGN KEY → todo_templates.template_id |
| user_id | VARCHAR(100) | 用户ID | NOT NULL |
| remind_time | TIMESTAMP | 提醒时间 | NOT NULL |
| ddl_time | TIMESTAMP | 截止时间 | NOT NULL |
| status | ENUM | 任务状态 | CHECK IN ('pending', 'completed', 'revoked', 'escalated') |
| created_at | TIMESTAMP | 创建时间 | DEFAULT NOW() |
| updated_at | TIMESTAMP | 更新时间 | DEFAULT NOW(), ON UPDATE NOW() |

**索引**:
- `idx_todos_user_status` ON (user_id, status)
- `idx_todos_status_ddl` ON (status, ddl_time)

**状态说明**:
- `pending`: 待完成
- `completed`: 已完成
- `revoked`: 已撤销（模板被禁用时）
- `escalated`: 已升级（超过截止时间）

**示例数据**:
```python
todo = Todo(
    template_id=1,
    user_id="U123456",
    remind_time=datetime(2025, 11, 22, 9, 0),
    ddl_time=datetime(2025, 11, 22, 9, 30),
    status=TodoStatus.PENDING
)
```

### 3. todo_status_logs（状态变更日志）

记录任务状态的所有变更历史。

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| log_id | INTEGER | 日志ID | PRIMARY KEY, AUTO_INCREMENT |
| todo_id | INTEGER | 关联任务ID | FOREIGN KEY → todos.todo_id |
| old_status | ENUM | 旧状态 | CHECK IN ('pending', 'completed', 'revoked', 'escalated'), NULLABLE |
| new_status | ENUM | 新状态 | CHECK IN ('pending', 'completed', 'revoked', 'escalated') |
| changed_at | TIMESTAMP | 变更时间 | DEFAULT NOW() |

**索引**:
- `idx_logs_todo_id` ON (todo_id)

**注意**: `old_status` 可以为 NULL（任务首次创建时）。

## ORM 模型使用

### 定义位置
所有模型定义在 `src/alfred/task/vault/models.py`。

### 基本用法

```python
from alfred.task.vault import get_vault
from alfred.task.vault.models import TodoTemplate, Todo, TodoStatus
from sqlalchemy import select

vault = get_vault()

# 创建新模板
with vault.db as session:
    template = TodoTemplate(
        user_id="U123456",
        content="每日站会",
        cron="0 9 * * 1-5",
        ddl_offset="30m"
    )
    session.add(template)

# 查询任务
with vault.db as session:
    todos = session.execute(
        select(Todo).where(Todo.status == TodoStatus.PENDING)
    ).scalars().all()

# 更新状态
with vault.db as session:
    todo = session.get(Todo, todo_id)
    todo.status = TodoStatus.COMPLETED
```

## 关系说明

- **TodoTemplate ↔ Todo**: 一对多关系
  - 一个模板可以生成多个任务实例
  - `template.todos` 访问所有关联任务
  - `todo.template` 访问所属模板

- **Todo ↔ TodoStatusLog**: 一对多关系
  - 一个任务可以有多条状态变更记录
  - `todo.logs` 访问所有日志
  - `log.todo` 访问关联任务

## 数据库配置

### SQLite（开发/测试）
```yaml
# config.yaml
vault:
  path: "sqlite:///prod.db"
```

### PostgreSQL（生产）
```yaml
# config.yaml
vault:
  path: "postgresql://alfred:alfred@localhost:5432/alfred"
```

## 迁移和初始化

数据库表结构由 SQLAlchemy 自动管理：
```python
from alfred.task.vault.models import Base
from alfred.task.vault import get_vault

vault = get_vault()
# 自动创建所有表（如果不存在）
Base.metadata.create_all(vault.engine)
```

系统启动时会自动执行此操作。
