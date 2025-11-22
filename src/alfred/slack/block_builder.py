from abc import ABC, abstractmethod

class BlockStyle(ABC):
    @abstractmethod
    def build_notify_blocks(self, normal_todos, overdue_todos):
        pass

    @abstractmethod
    def build_single_todo_blocks(self, todo, is_overdue=False):
        pass

    @abstractmethod
    def build_summary_blocks(self, todos_today):
        pass


class StandardBlockStyle(BlockStyle):
    """
    Build Slack blocks for todos (Standard Style).
    """

    def build_notify_blocks(self, normal_todos, overdue_todos):
        blocks = []
        if not normal_todos and not overdue_todos:
            return blocks

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔔 待办事项提醒"},
            }
        )

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 紧急：已逾期"},
            }
        )

        if not overdue_todos:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "_已逾期任务不重复提醒_"},
                }
            )
        else:
            for todo in overdue_todos:
                blocks.extend(self.build_single_todo_blocks(todo))
                blocks.append({"type": "divider"})

        blocks.append(
            {"type": "header", "text": {"type": "plain_text", "text": "📋 普通待办"}}
        )

        if not normal_todos:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "_已提醒任务不重复提醒_"},
                }
            )
        else:
            for todo in normal_todos:
                blocks.extend(self.build_single_todo_blocks(todo))
                blocks.append({"type": "divider"})

        if blocks and blocks[-1]["type"] == "divider":
            blocks.pop()

        return blocks

    def build_single_todo_blocks(self, todo, is_overdue=False):
        todo_id = todo.get("todo_id")
        user_id = todo.get("user_id")
        todo_content = todo.get("todo_content")
        status = todo.get("status")

        section_block_id = f"todo_section_{todo_id}"

        accessory = (
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Complete"},
                "style": "primary",
                "action_id": "mark_todo_complete",
                "value": str(todo_id),
            }
            if status == "pending"
            else {
                "type": "button",
                "text": {"type": "plain_text", "text": "↩️ Undo"},
                "style": "danger",
                "action_id": "mark_todo_undo",
                "value": str(todo_id),
            }
        )

        status_emoji_map = {
            "pending": "⏳ Pending",
            "completed": "✅ Completed",
            "revoked": "↩️ Revoked",
        }
        status_display = status_emoji_map.get(status, status)

        if status in ("completed", "revoked"):
            text_content_display = f"~{todo_content}~"
        else:
            text_content_display = f"*{todo_content}*"

        metadata_display = (
            f"> *By*: <@{user_id}> | *ID*: {todo_id} | *Status*: {status_display}"
        )

        section_block = {
            "type": "section",
            "block_id": section_block_id,
            "text": {
                "type": "mrkdwn",
                "text": f"{text_content_display}\n{metadata_display}",
            },
            "accessory": accessory,
        }
        return [section_block]

    def build_summary_blocks(self, todos_today):
        blocks = []
        if not todos_today:
            return blocks
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 每日总结"},
            }
        )
        for todo in todos_today:
            blocks.extend(self.build_single_todo_blocks(todo))

        total = len(todos_today)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"总计: {total} 个任务"}]
        })
        return blocks


class SaaSBlockStyle(BlockStyle):
    """
    Build Slack blocks with a clean 'SaaS/Developer' aesthetic.
    Using Inline Code styles for badges instead of emojis.
    """

    def build_notify_blocks(self, normal_todos, overdue_todos):
        blocks = []
        if not normal_todos and not overdue_todos:
            return blocks

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "TASK DIGEST"},
            }
        )
        blocks.append({"type": "divider"})

        if overdue_todos:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*⚠️ Requires Attention*"},
                }
            )
            for todo in overdue_todos:
                blocks.extend(self.build_single_todo_blocks(todo, is_overdue=True))

        if normal_todos:
            if overdue_todos:
                blocks.append({"type": "divider"})
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "*Upcoming*"},
                    }
                )

            for todo in normal_todos:
                blocks.extend(self.build_single_todo_blocks(todo, is_overdue=False))

        total = len(normal_todos) + len(overdue_todos)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Total: {total}"}]
        })

        return blocks

    def build_single_todo_blocks(self, todo, is_overdue=False):
        todo_id = todo.get("todo_id")
        user_id = todo.get("user_id")
        todo_content = todo.get("todo_content")
        status = todo.get("status")
        due_time = todo.get("due_time", "No Date")

        if is_overdue:
            status_badge = "` 🚨 OVERDUE ` "
        else:
            status_badge = "` PENDING ` "

        if status == "completed":
            content_display = f"~{todo_content}~"
            status_badge = "` DONE ` "
        else:
            content_display = f"{todo_content}"

        if status == "pending":
            btn_text = "Done"
            btn_style = "primary"
            action = "mark_todo_complete"
        else:
            btn_text = "Undo"
            btn_style = "danger"
            action = "mark_todo_undo"

        accessory = {
            "type": "button",
            "text": {"type": "plain_text", "text": btn_text},
            "style": btn_style,
            "action_id": action,
            "value": str(todo_id),
        }

        text_block = (
            f"<@{user_id}> *{content_display}*\n"
            f"{status_badge}  ` 📅 {due_time} `  ` #{todo_id} `"
        )

        section_block = {
            "type": "section",
            "block_id": f"todo_section_{todo_id}",
            "text": {
                "type": "mrkdwn",
                "text": text_block
            },
            "accessory": accessory,
        }

        return [section_block]

    def build_summary_blocks(self, todos_today):
        blocks = []
        if not todos_today:
            return blocks
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Daily Summary"},
            }
        )
        for todo in todos_today:
            blocks.extend(self.build_single_todo_blocks(todo))

        total = len(todos_today)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Total tasks: {total}"}]
        })
        return blocks


class GitFlowBlockStyle(BlockStyle):
    """
    Build Slack blocks with a 'Modern Dev / Git Flow' aesthetic.
    Clean, structured, and typography-focused.
    """

    def build_notify_blocks(self, normal_todos, overdue_todos):
        blocks = []
        if not normal_todos and not overdue_todos:
            return blocks

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📋 Task Manifest"},
            }
        )

        if overdue_todos:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "🚨 *Critical / Overdue*"}],
                }
            )
            for todo in overdue_todos:
                blocks.extend(
                    self.build_single_todo_blocks(todo, is_overdue=True)
                )

            if normal_todos:
                blocks.append({"type": "divider"})

        if normal_todos:
            if overdue_todos:
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": "🔹 *Backlog / Pending*"}
                        ],
                    }
                )

            for todo in normal_todos:
                blocks.extend(
                    self.build_single_todo_blocks(todo, is_overdue=False)
                )

        total = len(normal_todos) + len(overdue_todos)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Commit check: {total} files changed."}
                ],
            }
        )

        return blocks

    def build_single_todo_blocks(self, todo, is_overdue=False):
        todo_id = todo.get("todo_id")
        user_id = todo.get("user_id")
        todo_content = todo.get("todo_content")
        status = todo.get("status")
        due_time = todo.get("remind_time")

        if status == "pending":
            btn_text = "Close Issue"
            btn_style = "primary"
            action = "mark_todo_complete"
        else:
            btn_text = "Reopen"
            btn_style = "danger"
            action = "mark_todo_undo"

        accessory = {
            "type": "button",
            "text": {"type": "plain_text", "text": btn_text},
            "style": btn_style,
            "action_id": action,
            "value": str(todo_id),
        }

        id_badge = f"` #{todo_id} `"

        if is_overdue:
            time_display = f"*{due_time.strftime('%Y-%m-%d %H:%M:%S')}*"
        else:
            time_display = f"{due_time.strftime('%Y-%m-%d %H:%M:%S')}"

        text_block = (
            f"> {id_badge}  <@{user_id}>  `::`  *{todo_content}*\n"
            f"> ` └── `{time_display}"
        )
    
        section_block = {
            "type": "section",
            "block_id": f"todo_section_{todo_id}",
            "text": {"type": "mrkdwn", "text": text_block},
            "accessory": accessory,
        }

        return [section_block]

    def build_summary_blocks(self, todos_today):
        blocks = []
        if not todos_today:
            return blocks

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Daily Summary"},
            }
        )

        for todo in todos_today:
            blocks.extend(self.build_single_todo_blocks(todo))

        total = len(todos_today)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Summary complete: {total} tasks reviewed.",
                    }
                ],
            }
        )

        return blocks


class BlockBuilder:
    _style = GitFlowBlockStyle()

    @classmethod
    def set_style(cls, style_name: str):
        """
        Set the block style.
        Options: 'standard', 'saas', 'gitflow'
        """
        if style_name.lower() == "standard":
            cls._style = StandardBlockStyle()
        elif style_name.lower() == "saas":
            cls._style = SaaSBlockStyle()
        elif style_name.lower() == "gitflow":
            cls._style = GitFlowBlockStyle()
        else:
            raise ValueError(f"Unknown style: {style_name}")

    @classmethod
    def build_notify_blocks(cls, normal_todos, overdue_todos):
        return cls._style.build_notify_blocks(normal_todos, overdue_todos)

    @classmethod
    def build_single_todo_blocks(cls, todo, is_overdue=False):
        return cls._style.build_single_todo_blocks(todo, is_overdue)

    @classmethod
    def build_summary_blocks(cls, todos_today):
        return cls._style.build_summary_blocks(todos_today)
