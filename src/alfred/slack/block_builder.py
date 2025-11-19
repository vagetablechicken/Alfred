# class BlockBuilder:
#     """
#     Build Slack blocks for todos.
#     """

#     @staticmethod
#     def build_notify_blocks(normal_todos, overdue_todos):
#         """build notification blocks for normal and overdue todos"""
#         blocks = []
#         if not normal_todos and not overdue_todos:
#             return blocks

#         blocks.append(
#             {
#                 "type": "header",
#                 "text": {"type": "plain_text", "text": "🔔 待办事项提醒"},
#             }
#         )

#         blocks.append(
#             {
#                 "type": "header",
#                 "text": {"type": "plain_text", "text": "🚨 紧急：已逾期"},
#             }
#         )

#         if not overdue_todos:
#             blocks.append(
#                 {
#                     "type": "section",
#                     "text": {"type": "mrkdwn", "text": "_已逾期任务不重复提醒_"},
#                 }
#             )
#         else:
#             for todo in overdue_todos:
#                 blocks.extend(BlockBuilder.build_single_todo_blocks(todo))
#                 blocks.append({"type": "divider"})

#         blocks.append(
#             {"type": "header", "text": {"type": "plain_text", "text": "📋 普通待办"}}
#         )

#         if not normal_todos:
#             blocks.append(
#                 {
#                     "type": "section",
#                     "text": {"type": "mrkdwn", "text": "_已提醒任务不重复提醒_"},
#                 }
#             )
#         else:
#             for todo in normal_todos:
#                 blocks.extend(BlockBuilder.build_single_todo_blocks(todo))
#                 blocks.append({"type": "divider"})

#         if blocks[-1]["type"] == "divider":
#             blocks.pop()

#         return blocks

#     @staticmethod
#     def build_single_todo_blocks(todo):
#         """build blocks for a single todo with status-based accessory"""
#         todo_id = todo["todo_id"]
#         user_id = todo["user_id"]
#         todo_content = todo["todo_content"]
#         status = todo["status"]

#         section_block_id = f"todo_section_{todo_id}"

#         accessory = (
#             {
#                 "type": "button",
#                 "text": {"type": "plain_text", "text": "✅ Complete"},
#                 "style": "primary",
#                 "action_id": "mark_todo_complete",
#                 "value": str(todo_id),
#             }
#             if status == "pending"
#             else {
#                 "type": "button",
#                 "text": {"type": "plain_text", "text": "↩️ Undo"},
#                 "style": "danger",
#                 "action_id": "mark_todo_undo",
#                 "value": str(todo_id),
#             }
#         )

#         status_emoji_map = {
#             "pending": "⏳ Pending",
#             "completed": "✅ Completed",
#             "revoked": "↩️ Revoked",
#         }
#         status_display = status_emoji_map.get(status, status)

#         if status in ("completed", "revoked"):
#             text_content_display = f"~{todo_content}~"
#         else:
#             text_content_display = f"*{todo_content}*"

#         metadata_display = (
#             f"> *By*: <@{user_id}> | *ID*: {todo_id} | *Status*: {status_display}"
#         )

#         section_block = {
#             "type": "section",
#             "block_id": section_block_id,
#             "text": {
#                 "type": "mrkdwn",
#                 "text": f"{text_content_display}\n{metadata_display}",
#             },
#             "accessory": accessory,
#         }
#         return [section_block]


# class BlockBuilder:
#     """
#     Build Slack blocks with a clean 'SaaS/Developer' aesthetic.
#     Using Inline Code styles for badges instead of emojis.
#     """

#     @staticmethod
#     def build_notify_blocks(normal_todos, overdue_todos):
#         blocks = []
#         if not normal_todos and not overdue_todos:
#             return blocks

#         # 极简 Header，全大写，字间距感
#         blocks.append(
#             {
#                 "type": "header",
#                 "text": {"type": "plain_text", "text": "TASK DIGEST"},
#             }
#         )
#         blocks.append({"type": "divider"})

#         # --- 1. 逾期部分 ---
#         if overdue_todos:
#             blocks.append(
#                 {
#                     "type": "section",
#                     "text": {"type": "mrkdwn", "text": "*⚠️ Requires Attention*"},
#                 }
#             )
#             for todo in overdue_todos:
#                 blocks.extend(BlockBuilder.build_single_todo_blocks(todo, is_overdue=True))

#         # --- 2. 普通部分 ---
#         if normal_todos:
#             if overdue_todos:
#                 blocks.append({"type": "divider"})
#                 blocks.append(
#                     {
#                         "type": "section",
#                         "text": {"type": "mrkdwn", "text": "*Upcoming*"},
#                     }
#                 )

#             for todo in normal_todos:
#                 blocks.extend(BlockBuilder.build_single_todo_blocks(todo, is_overdue=False))

#         # 极简 Footer
#         total = len(normal_todos) + len(overdue_todos)
#         blocks.append({
#             "type": "context",
#             "elements": [{"type": "mrkdwn", "text": f"Total: {total}"}]
#         })

#         return blocks

#     @staticmethod
#     def build_single_todo_blocks(todo, is_overdue=False):
#         todo_id = todo.get("todo_id")
#         user_id = todo.get("user_id")
#         todo_content = todo.get("todo_content")
#         status = todo.get("status")
#         due_time = todo.get("due_time", "No Date")

#         # --- 核心设计：构造“胶囊标签” ---
#         # 使用 `text` 语法包裹文本，在 Slack 里会渲染成红字或灰底文字
#         if is_overdue:
#             # 逾期使用显眼的标签
#             status_badge = "` 🚨 OVERDUE ` "
#         else:
#             # 普通任务使用普通标签
#             status_badge = "` PENDING ` "

#         if status == "completed":
#             content_display = f"~{todo_content}~"
#             status_badge = "` DONE ` "
#         else:
#             content_display = f"{todo_content}"

#         # 按钮样式：简洁化
#         if status == "pending":
#             btn_text = "Done"
#             btn_style = "primary"
#             action = "mark_todo_complete"
#         else:
#             btn_text = "Undo"
#             btn_style = "danger"
#             action = "mark_todo_undo"

#         accessory = {
#             "type": "button",
#             "text": {"type": "plain_text", "text": btn_text},
#             "style": btn_style,
#             "action_id": action,
#             "value": str(todo_id),
#         }

#         # --- 布局逻辑 ---
#         # Line 1: <@User> Task Content (强调人与事)
#         # Line 2: [STATUS]  [TIME]  [ID] (参数栏，对齐感强)
#         # 这种两行结构在一个 text block 里，行间距比 context block 更紧凑，更有整体感

#         text_block = (
#             f"<@{user_id}> *{content_display}*\n"
#             f"{status_badge}  ` 📅 {due_time} `  ` #{todo_id} `"
#         )

#         section_block = {
#             "type": "section",
#             "text": {
#                 "type": "mrkdwn",
#                 "text": text_block
#             },
#             "accessory": accessory,
#         }

#         return [section_block]


class BlockBuilder:
    """
    Build Slack blocks with a 'Modern Dev / Git Flow' aesthetic.
    Clean, structured, and typography-focused.
    """

    @staticmethod
    def build_notify_blocks(normal_todos, overdue_todos):
        blocks = []
        if not normal_todos and not overdue_todos:
            return blocks

        # Header: 极简风格，像 README 的标题
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📋 Task Manifest"},
            }
        )

        # 1. 逾期部分
        if overdue_todos:
            # 使用 Context 加上 Alert 图标，而不是巨大的 Section
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "🚨 *Critical / Overdue*"}],
                }
            )
            for todo in overdue_todos:
                blocks.extend(
                    BlockBuilder.build_single_todo_blocks(todo, is_overdue=True)
                )

            # 只有当还有普通任务时，才加分割空隙
            if normal_todos:
                blocks.append({"type": "divider"})

        # 2. 普通部分
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
                    BlockBuilder.build_single_todo_blocks(todo, is_overdue=False)
                )

        # Footer
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

    @staticmethod
    def build_single_todo_blocks(todo, is_overdue=False):
        todo_id = todo.get("todo_id")
        user_id = todo.get("user_id")
        todo_content = todo.get("todo_content")
        status = todo.get("status")
        due_time = todo.get("remind_time", "No Date")

        # 按钮逻辑
        if status == "pending":
            # 逾期用红色文字提醒，普通用绿色
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

        # --- 极客美学核心 ---
        # 1. ID 必须像 Git Hash 一样显示：` #101 `
        # 2. User 和 Content 之间用编程符号连接： :: 或 ->
        # 3. 使用 Quote (>) 包裹整个 Block，让它看起来像一个引用的代码块，左侧会有灰线

        # 格式设计：
        # > ` #ID `  **@User** ::  **Task Content**
        # > └── 🕒 Time

        # 这种树状结构 (└──) 是终端里最常见的表示层级的方式，非常 Geek

        # 逾期的话，ID 可以加粗或者用 Emoji 稍微修饰，但不要太花
        id_badge = f"` #{todo_id} `"

        if is_overdue:
            # 逾期时，时间加粗显示
            time_display = f"*{due_time}*"
        else:
            time_display = f"{due_time}"

        # 构造 Text
        # 第一行：索引 + 人 + 任务 (平级，高亮)
        # 第二行：分支符号 + 时间
        text_block = (
            f"> {id_badge}  <@{user_id}>  `::`  *{todo_content}*\n"
            f"> ` └── ` 🕒 {time_display}"
        )

        section_block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text_block},
            "accessory": accessory,
        }

        return [section_block]

    def build_summary_blocks(todos_today):
        """build end-of-day summary blocks"""
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
            blocks.extend(BlockBuilder.build_single_todo_blocks(todo))

        # Footer
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
