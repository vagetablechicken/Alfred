from contextlib import contextmanager
import logging
from datetime import datetime

from ..task.bulletin import Bulletin


class Butler:
    """
    Patrol bulletin and manage Slack interactions.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bulletin = Bulletin()
        self.sent_notifies = {"normal": set(), "overdue": set()}
        self.sent_summaries = set()

    @contextmanager
    def gather_notify_blocks(self):
        """gather overdue tasks as Slack blocks"""
        current_time = datetime.now()
        todos_today = self.bulletin.get_todos(current_time.date())

        # filter overdue tasks, some todos have already been reminded, skip those
        normal_todos = [
            todo
            for todo in todos_today
            if todo["remind_time"] <= current_time < todo["ddl_time"]
            and todo["id"] not in self.sent_notifies["normal"]
        ]
        overdue_todos = [
            todo
            for todo in todos_today
            if todo["ddl_time"] <= current_time
            and todo["id"] not in self.sent_notifies["overdue"]
        ]
        # build blocks
        blocks = self._build_blocks(normal_todos, overdue_todos)
        try:
            yield blocks

        except Exception as e:
            self.logger.error(f"[Butler] ERROR sending blocks: {e}")
        else:
            self.logger.info("[Butler] Successfully sent, update status.")
            # mark reminders as sent
            for todo in normal_todos:
                self.sent_notifies["normal"].add(todo["id"])
            for todo in overdue_todos:
                self.sent_notifies["overdue"].add(todo["id"])
            self.logger.debug(f"[Butler] Updated sent_notifies: {self.sent_notifies}")

    @contextmanager
    def gather_end_of_day_summary(self):
        """gather end-of-day summary as Slack blocks"""
        current_time = datetime.now()
        blocks = []
        try:
            if (
                current_time.date() not in self.sent_summaries
                and current_time.hour >= 18
            ):
                blocks.append(
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "📊 今日任务总结"},
                    }
                )
                todos_today = self.bulletin.get_todos(current_time.date())
                for todo in todos_today:
                    blocks.extend(self._build_single_todo_blocks(todo))
                    blocks.append({"type": "divider"})
                if blocks[-1]["type"] == "divider":
                    blocks.pop()
            yield blocks
        except Exception as e:
            self.logger.error(f"[Butler] ERROR sending end-of-day summary: {e}")
        else:
            self.logger.info("[Butler] Successfully sent end-of-day summary.")
            if blocks:
                self.sent_summaries.add(current_time.date())
                self.logger.debug(
                    f"[Butler] Updated sent_summaries: {self.sent_summaries}"
                )

    def _build_blocks(self, normal_todos, overdue_todos):
        """interactive block building"""
        blocks = []

        # 1. 添加一个固定的主标题
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔔 您的待办事项提醒"},
            }
        )

        # --- 2. 逾期任务 (Overdue) 区块 ---
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 紧急：已逾期"},
            }
        )

        if not overdue_todos:
            # 如果没有逾期任务，显示一条友好消息
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "_太好了! 没有逾期的任务。_"},
                }
            )
        else:
            # 循环遍历所有逾期任务
            for todo in overdue_todos:
                # 调用辅助函数来生成该任务的 blocks
                blocks.extend(self._build_single_todo_blocks(todo))
                # 在每个任务后添加一个分隔线
                blocks.append({"type": "divider"})

        # --- 3. 普通任务 (Normal) 区块 ---
        blocks.append(
            {"type": "header", "text": {"type": "plain_text", "text": "📋 普通待办"}}
        )

        if not normal_todos:
            # 如果没有普通任务
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "_所有任务都已清空!_"},
                }
            )
        else:
            # 循环遍历所有普通任务
            for todo in normal_todos:
                blocks.extend(self._build_single_todo_blocks(todo))
                blocks.append({"type": "divider"})

        # 清理：移除最后多余的那个分隔线
        if blocks[-1]["type"] == "divider":
            blocks.pop()

        return blocks

    def _build_single_todo_blocks(self, todo):
        """
        辅助函数：为 *单个* todo 项目创建 [section, actions] 块, 完全根据todo的状态。
        """
        # 从 todo 对象中提取信息
        todo_id = todo["todo_id"]
        todo_content = todo["todo_content"]
        status = todo["status"]

        # 为 block_id 使用唯一的 ID (好习惯)
        section_block_id = f"todo_section_{todo_id}"
        action_block_id = f"todo_action_{todo_id}"

        # 1. 信息区块 (Section Block)
        #    完全按照你的示例格式
        section_block = {
            "type": "section",
            "block_id": section_block_id,
            "text": {
                "type": "mrkdwn",
                "text": f"*[ID: {todo_id}]* `{todo_content}`\n*Status*: {status}",
            },
        }
        if status == "revoked":
            section_block["text"]["text"] += " (↩️ Revoked)"
            return [section_block]  # 撤销状态不需要动作区块

        # 2. 动作区块 (Actions Block)
        # text, buttons 根据状态变化
        if status == "pending":
            action_block = {
                "type": "actions",
                "block_id": action_block_id,
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Complete"},
                        "style": "primary",
                        # 'action_id' 告诉 Bolt 你的监听器要捕获什么
                        "action_id": "mark_todo_complete",
                        # 'value' 告诉 Bolt 你在操作 *哪一个* todo
                        "value": str(todo_id),
                    },
                ],
            }
        elif status == "completed":
            action_block = {
                "type": "actions",
                "block_id": action_block_id,
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "↩️ Undo"},
                        "style": "danger",
                        "action_id": "mark_todo_undo",
                        "value": str(todo_id),
                    }
                ],
            }
        else:
            raise ValueError(f"Unknown todo status: {status}")

        # 返回一个列表，包含这个 todo 的所有 blocks
        return [section_block, action_block]

    def build_single_todo_blocks(self, todo_id: int):
        """build blocks for a single todo by id"""
        todo = self.bulletin.get_todo(todo_id)
        if not todo:
            raise ValueError(f"Todo with id {todo_id} not found.")
        return self._build_single_todo_blocks(todo)

    def mark_todo_complete(self, todo_id: int):
        """mark a task as completed"""
        self.bulletin.complete_todo(todo_id, datetime.now())

    def mark_todo_undo(self, todo_id: int):
        """undo a task completion"""
        self.bulletin.revert_todo_completion(todo_id, datetime.now())

    def add_template(self, user_id, name, cron, ddl_offset, run_once):
        return self.bulletin.add_template(user_id, name, cron, ddl_offset, run_once)

    def get_todos(self, for_date):
        return self.bulletin.get_todos(for_date)

    def get_templates(self):
        return self.bulletin.get_templates()

    def get_todo_log(self, todo_id):
        return self.bulletin.get_todo_log(todo_id)


butler = Butler()
