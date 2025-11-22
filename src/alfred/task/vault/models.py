import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# 1. 定义基础类
class Base(DeclarativeBase):
    pass


# 2. 定义状态枚举 (对应 SQL 中的 CHECK 约束)
class TodoStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REVOKED = "revoked"
    ESCALATED = "escalated"


# ---------------------------------------------------------
# Table 1: 任务模板 (Cron)
# ---------------------------------------------------------
class TodoTemplate(Base):
    __tablename__ = "todo_templates"

    # 对应: template_id INTEGER PRIMARY KEY AUTOINCREMENT
    id: Mapped[int] = mapped_column("template_id", primary_key=True)

    # 对应: content TEXT NOT NULL
    content: Mapped[str] = mapped_column("content", Text, nullable=False)

    # 对应: user_id TEXT NOT NULL (给 String 加长度是为了兼容 Postgres)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # 对应: cron TEXT NOT NULL
    cron: Mapped[str] = mapped_column(String(100), nullable=False)

    # 对应: ddl_offset TEXT NOT NULL
    ddl_offset: Mapped[str] = mapped_column(String(50), nullable=False)

    # 对应: run_once INTEGER DEFAULT 0 (用 Boolean 映射)
    run_once: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 对应: is_active INTEGER DEFAULT 1
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 对应: created_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    # 【ORM 关系】: 一个模板可以生成多个 Todo
    todos: Mapped[List["Todo"]] = relationship(back_populates="template")

    # 【索引】: 对应 CREATE INDEX idx_templates_user_active
    __table_args__ = (Index("idx_templates_user_active", "user_id", "is_active"),)


# ---------------------------------------------------------
# Table 2: 任务实例 (Instance)
# ---------------------------------------------------------
class Todo(Base):
    __tablename__ = "todos"

    # 对应: todo_id INTEGER PRIMARY KEY
    id: Mapped[int] = mapped_column("todo_id", primary_key=True)

    # 对应: template_id INTEGER NOT NULL
    template_id: Mapped[int] = mapped_column(
        ForeignKey("todo_templates.template_id"), nullable=False
    )

    user_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # 对应: remind_time / ddl_time
    # SQLAlchemy 会自动处理: 在 SQLite 存字符串, 在 Postgres 存 TIMESTAMP
    remind_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ddl_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 对应: status ... CHECK(...)
    # 使用 Python Enum 既保证了类型安全，SQLAlchemy 也会自动生成 CHECK 约束
    status: Mapped[TodoStatus] = mapped_column(
        SAEnum(TodoStatus), default=TodoStatus.PENDING, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # ORM 
    template: Mapped["TodoTemplate"] = relationship(back_populates="todos")
    logs: Mapped[List["TodoStatusLog"]] = relationship(back_populates="todo")

    # indexes
    __table_args__ = (
        Index("idx_todos_user_status", "user_id", "status"),
        Index("idx_todos_status_ddl", "status", "ddl_time"),
    )


# ---------------------------------------------------------
# Table 3: 状态变更日志 (Logs)
# ---------------------------------------------------------
class TodoStatusLog(Base):
    __tablename__ = "todo_status_logs"

    id: Mapped[int] = mapped_column("log_id", primary_key=True)

    todo_id: Mapped[int] = mapped_column(ForeignKey("todos.todo_id"), nullable=False)

    old_status: Mapped[Optional[TodoStatus]] = mapped_column(
        SAEnum(TodoStatus), nullable=True
    )
    new_status: Mapped[TodoStatus] = mapped_column(SAEnum(TodoStatus), nullable=False)

    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 【ORM 关系】
    todo: Mapped["Todo"] = relationship(back_populates="logs")

    # 【索引】
    __table_args__ = (Index("idx_logs_todo_id", "todo_id"),)
