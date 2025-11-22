from contextlib import contextmanager
import logging
from datetime import datetime, time

from alfred.slack.block_builder import BlockBuilder
from alfred.task.bulletin import Bulletin


class Butler:
    """
    Patrol bulletin and manage Slack interactions.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bulletin = Bulletin()
        self.sent_notifies = {"normal": set(), "overdue": set()}
        self.sent_summaries = set()
        self.summary_time = time(hour=18, minute=0)  # 6 PM

    @contextmanager
    def gather_notify_blocks(self):
        """gather today pending todos as Slack blocks"""
        current_time = datetime.now()
        todos_today = self.bulletin.get_todos(current_time.date())

        # filter pending todos, some todos have already been reminded, skip those
        def need_normal_remind(todo):
            # todo times are str
            remind_time = datetime.fromisoformat(todo["remind_time"])
            ddl_time = datetime.fromisoformat(todo["ddl_time"])
            return (
                remind_time <= current_time < ddl_time
                and todo["todo_id"] not in self.sent_notifies["normal"]
                and todo["status"] == "pending"
            )

        def need_overdue_remind(todo):
            ddl_time = datetime.fromisoformat(todo["ddl_time"])
            return (
                ddl_time <= current_time
                and todo["todo_id"] not in self.sent_notifies["overdue"]
                and todo["status"] == "pending"
            )

        normal_todos = [todo for todo in todos_today if need_normal_remind(todo)]
        overdue_todos = [todo for todo in todos_today if need_overdue_remind(todo)]
        # build blocks
        blocks = BlockBuilder.build_notify_blocks(normal_todos, overdue_todos)
        try:
            yield blocks
        except Exception as e:
            self.logger.exception(f"[Butler] ERROR sending blocks: {e}")
            yield []
        else:
            if not blocks:
                self.logger.debug("[Butler] No new notifications to send.")
                return
            self.logger.info("[Butler] Successfully sent, update status.")
            # mark reminders as sent
            for todo in normal_todos:
                self.sent_notifies["normal"].add(todo["todo_id"])
            for todo in overdue_todos:
                self.sent_notifies["overdue"].add(todo["todo_id"])
            self.logger.debug(f"[Butler] Updated sent_notifies: {self.sent_notifies}")

    @contextmanager
    def gather_end_of_day_summary(self):
        """gather end-of-day summary as Slack blocks"""
        current_time = datetime.now()
        blocks = []
        try:
            if (
                current_time.date() not in self.sent_summaries
                and current_time.time() >= self.summary_time
            ):
                self.logger.info("[Butler] Gathering end-of-day summary.")
                todos_today = self.bulletin.get_todos(current_time.date())
                if todos_today:
                    blocks = BlockBuilder.build_summary_blocks(todos_today)
            yield blocks
        except Exception as e:
            self.logger.exception(f"[Butler] ERROR sending end-of-day summary: {e}")
            yield []
        else:
            if not blocks:
                self.logger.debug("[Butler] No end-of-day summary to send.")
                return
            self.logger.info("[Butler] Successfully sent end-of-day summary.")
            self.sent_summaries.add(current_time.date())
            self.logger.debug(f"[Butler] Updated sent_summaries: {self.sent_summaries}")

    def build_single_todo_blocks(self, todo_id: int):
        """build blocks for a single todo by id"""
        todo = self.bulletin.get_todo(todo_id)
        if not todo:
            raise ValueError(f"Todo with id {todo_id} not found.")
        return BlockBuilder.build_single_todo_blocks(todo)

    def replace_todo_blocks_in_message(
        self, original_blocks, todo_id: int, new_todo_blocks
    ):
        # single accessory blocks contains only section block
        section_block_id = f"todo_section_{todo_id}"
        new_blocks = []
        for block in original_blocks:
            if block.get("block_id") == section_block_id:
                new_blocks.extend(new_todo_blocks)
            else:
                new_blocks.append(block)
        return new_blocks

    def mark_todo_complete(self, todo_id: int):
        """mark a todo as completed"""
        self.bulletin.complete_todo(todo_id, datetime.now())

    def mark_todo_undo(self, todo_id: int):
        """undo a todo completion"""
        self.bulletin.revert_todo_completion(todo_id, datetime.now())

    def __getattr__(self, name):
        """Delegate attribute access to bulletin for convenience"""
        return getattr(self.bulletin, name)


butler = Butler()
