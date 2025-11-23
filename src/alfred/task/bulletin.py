from datetime import datetime, date, timedelta
import logging
from typing import List
from croniter import croniter

from sqlalchemy import select, func, Date

from alfred.task.vault import get_vault
from alfred.task.vault.models import (
    Todo,
    TodoTemplate,
    TodoStatusLog,
    TodoStatus,
)


class Bulletin:
    """
    Read raw meta data from singleton vault instance. Manage templates and todos.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.vault = get_vault()

    def run_in_session(self):
        """Provide a transactional session scope.

        Usage:
            with bulletin.run_in_session() as session:
                # perform operations
        """
        return self.vault.session_scope()

    def _parse_offset(self, offset_str: str) -> timedelta:
        """handle simple ddl_offset like '5m', '2h', '1d' etc."""
        unit = offset_str[-1]
        value = int(offset_str[:-1])
        if unit == "s":
            return timedelta(seconds=value)
        elif unit == "m":
            return timedelta(minutes=value)
        elif unit == "h":
            return timedelta(hours=value)
        elif unit == "d":
            return timedelta(days=value)
        else:
            raise ValueError(f"Unsupported offset unit: {unit}")

    def create_todo(
        self,
        session,
        user_id: str,
        template_id: int,
        ddl_offset: str,
        remind_time: datetime,
        create_time: datetime,
    ) -> int:
        """Create a new todo and its initial status log.

        Args:
            session: Active SQLAlchemy session
            user_id: User ID
            template_id: Template ID
            ddl_offset: Deadline offset string (e.g., '5m', '2h', '1d')
            remind_time: When to remind
            create_time: Creation timestamp

        Returns:
            Created todo ID
        """
        # Calculate DDL time
        ddl_time = remind_time + self._parse_offset(ddl_offset)

        # Create Todo object
        new_todo = Todo(
            template_id=template_id,
            user_id=user_id,
            status=TodoStatus.PENDING,
            remind_time=remind_time,
            ddl_time=ddl_time,
            created_at=create_time,
            updated_at=create_time,
        )
        session.add(new_todo)
        session.flush()
        todo_id = new_todo.id

        # Create status log
        new_log = TodoStatusLog(
            todo_id=todo_id,
            old_status=None,
            new_status=TodoStatus.PENDING,
            changed_at=create_time,
        )
        session.add(new_log)

        return todo_id

    def complete_todo(self, todo_id: int, current_time: datetime | str):
        """User completes a todo"""
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Completing Todo {todo_id} at {current_time} ---")
        try:
            with self.vault.session_scope() as session:
                todo = session.get(Todo, todo_id)
                if todo is None:
                    self.logger.error(f"ERROR: Todo {todo_id} not found.")
                    return

                old_status = todo.status
                if old_status in (TodoStatus.COMPLETED, TodoStatus.REVOKED):
                    self.logger.info(
                        f"Todo {todo_id} is already in a final state ({old_status.value})."
                    )
                    return

                todo.status = TodoStatus.COMPLETED
                todo.updated_at = current_time

                log = TodoStatusLog(
                    todo_id=todo_id,
                    old_status=old_status,
                    new_status=TodoStatus.COMPLETED,
                    changed_at=current_time,
                )
                session.add(log)

            self.logger.info(f"COMPLETED Todo {todo_id} (was {old_status.value})")
        except Exception as e:
            self.logger.error(f"ERROR completing Todo {todo_id}: {e}")

    def revert_todo_completion(self, todo_id: int, current_time: datetime | str):
        """user reverts a completed todo back to pending/escalated"""
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        self.logger.info(f"--- [USER] Reverting Todo {todo_id} at {current_time} ---")
        try:
            with self.vault.session_scope() as session:
                todo = session.get(Todo, todo_id)
                if todo is None:
                    self.logger.error(f"ERROR: Todo {todo_id} not found.")
                    return

                old_status = todo.status

                if old_status != TodoStatus.COMPLETED:
                    self.logger.error(
                        f"ERROR: Todo {todo_id} is not 'completed'. Cannot revert."
                    )
                    return

                todo.status = TodoStatus.PENDING
                todo.updated_at = current_time

                log = TodoStatusLog(
                    todo_id=todo_id,
                    old_status=old_status,
                    new_status=TodoStatus.PENDING,
                    changed_at=current_time,
                )
                session.add(log)

                self.logger.info(
                    f"REVERTED Todo {todo_id} from 'completed' back to 'pending'"
                )
        except Exception as e:
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
            with self.vault.session_scope() as session:
                template = session.get(TodoTemplate, template_id)
                if template is None:
                    self.logger.error(f"ERROR: Template {template_id} not found.")
                    return

                template.is_active = bool(is_active)

                todos_to_revoke: List[Todo] = []
                if not is_active:
                    todos_to_revoke = (
                        session.execute(
                            select(Todo).where(
                                Todo.template_id == template_id,
                                Todo.status.in_(
                                    [TodoStatus.PENDING, TodoStatus.ESCALATED]
                                ),
                            )
                        )
                        .scalars()
                        .all()
                    )

                    if not todos_to_revoke:
                        self.logger.info("No active todos to revoke.")

                    for todo in todos_to_revoke:
                        old_status = todo.status
                        self.logger.info(
                            f"REVOKING Todo {todo.id} (was {old_status.value})..."
                        )
                        todo.status = TodoStatus.REVOKED
                        todo.updated_at = current_time

                        log = TodoStatusLog(
                            todo_id=todo.id,
                            old_status=old_status,
                            new_status=TodoStatus.REVOKED,
                            changed_at=current_time,
                        )
                        session.add(log)

                self.logger.info(
                    f"Successfully set Template {template_id} active status to {is_active}"
                )
                if not is_active and todos_to_revoke:
                    self.logger.info(
                        f"Revoked {len(todos_to_revoke)} associated todos."
                    )
        except Exception as e:
            self.logger.error(f"ERROR changing template status: {e}")

    def add_template(self, user_id, content, cron, ddl_offset, run_once) -> int:
        """
        Add a new task template for a todo.
        Returns the template_id of the newly created template.
        """
        self.logger.info(f"Adding template for {user_id}: {content}")
        with self.vault.session_scope() as session:
            template = TodoTemplate(
                user_id=user_id,
                content=content,
                cron=cron,
                ddl_offset=ddl_offset,
                run_once=bool(int(run_once)),
            )
            session.add(template)
            session.flush()
            template_id = template.id
            self.logger.info(f"Added template {template_id} for {user_id}")
        return template_id

    def fetch_all(self):
        """
        Return dictionary of all tables and their rows.
        """
        self.logger.info(f"[QUERY] Fetching all data from all tables")
        all_data = {}
        with self.vault.session_scope() as session:
            templates = session.execute(select(TodoTemplate)).scalars().all()
            todos = session.execute(select(Todo)).scalars().all()
            logs = session.execute(select(TodoStatusLog)).scalars().all()

            all_data["todo_templates"] = [
                {
                    "template_id": t.id,
                    "user_id": t.user_id,
                    "content": t.content,
                    "cron": t.cron,
                    "ddl_offset": t.ddl_offset,
                    "is_active": t.is_active,
                    "run_once": t.run_once,
                    "created_at": t.created_at,
                }
                for t in templates
            ]

            all_data["todos"] = [
                {
                    "todo_id": td.id,
                    "template_id": td.template_id,
                    "user_id": td.user_id,
                    "remind_time": td.remind_time,
                    "ddl_time": td.ddl_time,
                    "status": td.status.value,
                    "created_at": td.created_at,
                    "updated_at": td.updated_at,
                }
                for td in todos
            ]

            all_data["todo_status_logs"] = [
                {
                    "log_id": l.id,
                    "todo_id": l.todo_id,
                    "old_status": (
                        l.old_status.value if l.old_status is not None else None
                    ),
                    "new_status": (l.new_status.value,),
                    "changed_at": l.changed_at,
                }
                for l in logs
            ]

        return all_data

    def get_templates(self):
        """get all todo templates"""
        self.logger.info(f"[QUERY] Getting all todo templates")
        with self.vault.session_scope() as session:
            templates = (
                session.execute(select(TodoTemplate).order_by(TodoTemplate.id))
                .scalars()
                .all()
            )
            return [
                {
                    "template_id": t.id,
                    "user_id": t.user_id,
                    "content": t.content,
                    "cron": t.cron,
                    "ddl_offset": t.ddl_offset,
                    "is_active": t.is_active,
                    "run_once": t.run_once,
                    "created_at": t.created_at,
                }
                for t in templates
            ]

    def get_active_templates(self, session):
        """Get all active templates (returns ORM objects).

        Args:
            session: Active SQLAlchemy session

        Returns:
            List of active TodoTemplate ORM objects
        """
        stmt = select(TodoTemplate).where(TodoTemplate.is_active == True)
        return session.execute(stmt).scalars().all()

    def check_todo_exists(
        self, session, user_id: str, template_id: int, remind_time: datetime
    ) -> bool:
        """Check if a todo already exists for given user/template/time.

        Args:
            session: Active SQLAlchemy session
            user_id: User ID
            template_id: Template ID
            remind_time: Remind time to check

        Returns:
            True if todo exists, False otherwise
        """
        stmt = select(Todo).where(
            Todo.user_id == user_id,
            Todo.template_id == template_id,
            Todo.remind_time == remind_time,
        )
        return session.execute(stmt).first() is not None

    def process_templates_in_session(
        self, session, current_time: datetime, template_processor
    ):
        """Process all active templates within a single session.

        This method allows the caller to provide a callback function to process each template,
        enabling complex operations (like scheduling) to be done atomically.

        Args:
            session: Active SQLAlchemy session
            current_time: Current timestamp for processing
            template_processor: Callable that takes (session, template, current_time)
                              and returns a dict with 'created' (bool) and optional 'message' (str)

        Returns:
            Dict with 'created_count' and 'results' list
        """
        active_templates = self.get_active_templates(session)
        created_count = 0
        results = []

        for template in active_templates:
            try:
                result = template_processor(session, template, current_time)
                if result.get("created", False):
                    created_count += 1
                results.append(result)
            except Exception as e:
                self.logger.error(
                    f"ERROR processing template {template.id} / {template.content}: {e}"
                )
                results.append(
                    {"created": False, "template_id": template.id, "error": str(e)}
                )

        return {"created_count": created_count, "results": results}

    def schedule_todos(self, current_time: datetime | str) -> int:
        """Schedule todos based on active templates using cron expressions.

        Args:
            current_time: Current timestamp for scheduling

        Returns:
            Number of todos created
        """
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)

        self.logger.info(f"[SCHEDULER] running at {current_time}")

        def process_template(session, template, current_time):
            user_id = template.user_id
            template_id = template.id
            cron = template.cron
            ddl_offset = template.ddl_offset
            content = template.content
            run_once = template.run_once

            # Use croniter to find the next time a todo should be scheduled
            cron_iter = croniter(cron, current_time)
            next_time = cron_iter.get_next(datetime)

            # Check if a todo already exists for this user/template/time
            if self.check_todo_exists(session, user_id, template_id, next_time):
                return {"created": False, "reason": "already_exists"}

            self.logger.info(
                f"[Scheduler] CREATING: Task for {user_id} ({content}) at {next_time}"
            )

            todo_id = self.create_todo(
                session,
                user_id,
                template_id,
                ddl_offset,
                remind_time=next_time,
                create_time=current_time,
            )

            self.logger.info(
                f"[Scheduler] Created todo ID {todo_id} for user {user_id}"
            )

            if run_once:
                self.logger.info(
                    f"[Scheduler] Disabling one-time template {template_id} for {user_id}"
                )
                template.is_active = False

            return {"created": True, "todo_id": todo_id}

        try:
            with self.run_in_session() as session:
                result = self.process_templates_in_session(
                    session, current_time, process_template
                )
                created_count = result["created_count"]

            if created_count == 0:
                self.logger.info("[Scheduler] No new todo to schedule at this time.")
            else:
                self.logger.info(f"[Scheduler] Created {created_count} new todo.")

            return created_count

        except Exception as e:
            self.logger.error(f"[Scheduler] DB ERROR: {e}")
            raise

    def get_todos(self, query_date: date | str = None):
        """get todos for a specific date (YYYY-MM-DD) or all if None"""
        if query_date and isinstance(query_date, str):
            query_date = date.fromisoformat(query_date)
        self.logger.info(f"[QUERY] Getting todos for reminder date: {query_date}")
        with self.vault.session_scope() as session:
            if query_date:
                rows = session.execute(
                    select(Todo, TodoTemplate)
                    .join(TodoTemplate, Todo.template_id == TodoTemplate.id)
                    .where(func.cast(Todo.remind_time, Date) == query_date)
                    .order_by(Todo.remind_time)
                ).all()
                result = [
                    {
                        "todo_id": td.id,
                        "template_id": tpl.id,
                        "content": tpl.content,
                        "user_id": td.user_id,
                        "status": td.status.value,
                        "remind_time": td.remind_time,
                        "ddl_time": td.ddl_time,
                    }
                    for td, tpl in rows
                ]
                return result
            else:
                rows = session.execute(
                    select(Todo, TodoTemplate)
                    .join(TodoTemplate, Todo.template_id == TodoTemplate.id)
                    .order_by(Todo.remind_time)
                ).all()
                result = [
                    {
                        "todo_id": td.id,
                        "template_id": tpl.id,
                        "content": tpl.content,
                        "user_id": td.user_id,
                        "remind_time": td.remind_time,
                        "ddl_time": td.ddl_time,
                        "status": td.status.value,
                        "created_at": td.created_at,
                        "updated_at": td.updated_at,
                    }
                    for td, tpl in rows
                ]
                return result

    def get_todo(self, todo_id: int):
        """get a specific todo by todo_id"""
        self.logger.info(f"[QUERY] Getting Todo {todo_id}")
        with self.vault.session_scope() as session:
            row = session.execute(
                select(Todo, TodoTemplate)
                .join(TodoTemplate, Todo.template_id == TodoTemplate.id)
                .where(Todo.id == todo_id)
            ).one_or_none()
            if not row:
                return None
            td, tpl = row
            return {
                "todo_id": td.id,
                "content": tpl.content,
                "user_id": td.user_id,
                "remind_time": td.remind_time,
                "ddl_time": td.ddl_time,
                "status": td.status.value,
                "created_at": td.created_at,
                "updated_at": td.updated_at,
            }

    def get_todo_log(self, todo_id: int):
        """get the status change log for a specific todo"""
        self.logger.info(f"[QUERY] Getting status log for Todo {todo_id}")
        with self.vault.session_scope() as session:
            logs = (
                session.execute(
                    select(TodoStatusLog)
                    .where(TodoStatusLog.todo_id == todo_id)
                    .order_by(TodoStatusLog.changed_at)
                )
                .scalars()
                .all()
            )
            return [
                {
                    "log_id": l.id,
                    "todo_id": l.todo_id,
                    # first todo log has no old_status
                    "old_status": (
                        l.old_status.value if l.old_status is not None else None
                    ),
                    "new_status": l.new_status.value,
                    "changed_at": l.changed_at,
                }
                for l in logs
            ]
