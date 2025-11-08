import os
import logging
from datetime import datetime
import sys
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from database_manager import DatabaseManager, TaskEngine

logging.basicConfig(level=logging.INFO)

assert os.environ.get("SLACK_APP_TOKEN") is not None, "SLACK_APP_TOKEN is required!"
assert os.environ.get("SLACK_BOT_TOKEN") is not None, "SLACK_BOT_TOKEN is required!"

dbm = DatabaseManager("tasks.db")
engine = TaskEngine(dbm)

app = App(token=os.environ["SLACK_BOT_TOKEN"])

BOT_USER_ID = None


# You ask me to get some information when I am mentioned
# I only talk to you, ephemeral messages
@app.event("app_mention")
def handle_app_mention(event, client):
    message_text = event.get("text", "")
    logging.info(f"App mentioned with message: {message_text}")
    if (
        message_text.lower().find("hi") != -1
        or message_text.lower().find("hello") != -1
    ):
        client.chat_postEphemeral(f"Hello there, <@{event['user']}>!")
    elif message_text.lower().find("list") != -1:
        todos = engine.get_todos(datetime.today().date())  # get all
        todo_list = (
            "\n".join([f"• {t[0]}" for t in todos]) if todos else "_No todos found._"
        )
        client.chat_postEphemeral(f"*Your Project TODOs today:* \n{todo_list}")
    else:
        help_message = (
            "Hi! I can help you with the following commands:\n"
            "• `hi` or `hello`: Greet me!\n"
            "• `list`: Get today's TODO list.\n"
            "Just mention me with one of these commands!"
        )
        client.chat_postEphemeral(help_message)


# let the channel know when someone reacts to todo messages
@app.event("reaction_added")
def handle_reaction_added(body, logger, client):
    """当有 emoji 被添加时触发"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        logger.warning("BOT_USER_ID is not set, skipping reaction check.")
        return

    event = body["event"]

    # 'item_user' 是被添加 reaction 的那条消息的“作者”
    message_author_id = event.get("item_user")

    # 'user' 是“添加” reaction 的那个人
    reactor_user_id = event.get("user")

    reaction = event.get("reaction")

    # 关键逻辑：检查这条消息的作者是不是我们的 Bot
    if message_author_id == BOT_USER_ID:
        logger.info(f"User <@{reactor_user_id}> ADDED ':{reaction}:' to MY message.")

        item = event.get("item", {})
        channel_id = item.get("channel")
        message_ts = item.get("ts")  # 这是原消息的 ts, 用作 thread_ts

        try:
            # chat:write 权限
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=f"Thanks for the ':{reaction}:' reaction, <@{reactor_user_id}>!",
            )
        except Exception as e:
            logger.error(f"Error posting reaction reply: {e}")


@app.event("reaction_removed")
def handle_reaction_removed(body, logger, client):
    """当有 emoji 被移除时触发"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        logger.warning("BOT_USER_ID is not set, skipping reaction check.")
        return

    event = body["event"]
    message_author_id = event.get("item_user")
    reactor_user_id = event.get("user")
    reaction = event.get("reaction")

    # 关键逻辑：检查这条消息的作者是不是我们的 Bot
    if message_author_id == BOT_USER_ID:
        logger.info(
            f"User <@{reactor_user_id}> REMOVED ':{reaction}:' from MY message."
        )

        client.chat_postMessage(
            channel=event["item"]["channel"],
            text=f"<@{reactor_user_id}> removed their ':{reaction}:' reaction.",
        )


# I don't care about normal messages, you can remove the event subscription if you want
# Just a protective handler
@app.event("message")
def handle_all_messages(message, say, logger):
    user_id = message.get("user")
    text = message.get("text", "")
    channel_id = message.get("channel")
    logger.info(f"Received a message from <@{user_id}> in channel {channel_id}: {text}")
    if message.get("bot_id") is not None:
        logger.debug("Ignoring message from a bot (or itself)")
        return
    logger.debug("No action taken for this message.")


def handle_add_template(args, user_id, logger, say):
    """处理添加任务模板的命令"""
    parts = args.split()
    if len(parts) < 4:
        say("Usage: /alfred add template <user_id> <name> <cron> <bias> [<run_once>]")
        return

    target_user_id = parts[0]
    name = parts[1]
    cron = parts[2]
    bias = parts[3]
    run_once = int(parts[4]) if len(parts) > 4 else 0

    template_id = engine.add_task_template(target_user_id, name, cron, bias, run_once)
    logger.info(
        f"User <@{user_id}> added template {template_id} for <@{target_user_id}>"
    )
    say(f"Template '{name}' added for <@{target_user_id}> with ID {template_id}.")


def handle_list(args, user_id, logger, say):
    """处理列出待办或模板的命令"""
    list_type = args.lower() if args else "todos"
    if list_type == "todos":
        todos = engine.get_todos(datetime.today().date())
        if not todos:
            say("You have no TODOs for today.")
            return
        todo_list = "\n".join([f"• ID {t[1]}: {t[0]}" for t in todos])
        say(f"*Your TODOs for today:*\n{todo_list}")
    elif list_type == "templates":
        templates = engine.get_task_templates(user_id)
        if not templates:
            say("You have no task templates.")
            return
        template_list = "\n".join(
            [
                f"• ID {t[0]}: {t[2]} (Cron: {t[3]}, Bias: {t[4]}, Run Once: {t[5]})"
                for t in templates
            ]
        )
        say(f"*Your Task Templates:*\n{template_list}")
    else:
        say("Unknown list type. Use 'todos' or 'templates'.")


def handle_log(args, user_id, logger, say):
    """处理标记待办为已完成的命令"""
    parts = args.split()
    if len(parts) != 1:
        say("Usage: /alfred log <todo_id>")
        return

    todo_id = parts[0]
    todo_log = engine.get_todo_log(todo_id)
    if not todo_log:
        say(f"No TODO found with ID {todo_id}.")
        return
    # 1. Prepare the log string first
    log_string = "\n".join(todo_log)

    # 2. Now the f-string is simple and readable
    say(f"""TODO log for ID {todo_id}:\n{log_string}""")


# ----------------------------------------------------
# Block Kit "沙盒"测试处理器
# ----------------------------------------------------
def handle_test_kit(user_id: str, logger: logging.Logger, say):
    """
    (新增) 处理 /alfred test
    发送一个硬编码的 Block Kit 消息用于测试，不查询数据库。
    """
    logger.info(f"User {user_id} triggered a Block Kit test.")

    # 1. 这是您要测试的 Block Kit
    todo_id = 999
    section_block_id = f"todo_{todo_id}_section"
    action_block_id = f"todo_{todo_id}_actions"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*这是一个用于测试的待办事项:*"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "block_id": section_block_id,
            "text": {
                "type": "mrkdwn",
                "text": f"*[ID: {todo_id}]* `测试任务`\n*状态*: pending",
            },
        },
        {
            "type": "actions",
            "block_id": action_block_id,
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Log (完成)"},
                    "action_id": "log_todo_button",
                    "value": str(todo_id),
                    "style": "primary",
                }
            ],
        },
    ]

    # 2. 发送这个 Block Kit (默认 ephemeral)
    try:
        say(text="Block Kit Test Message", blocks=blocks)
    except Exception as e:
        logger.error(f"Error posting TEST block kit: {e}")


@app.command("/alfred")
def handle_alfred_command(ack, body, client, logger, say):
    """
    处理 /alfred 命令
    'say' 在命令中默认是 ephemeral
    """
    # 立即 ACK (3秒内)
    ack()

    user_id = body["user_id"]
    text = body.get("text", "").strip()
    logger.info(f"User {user_id} triggered /alfred with: {text}")

    try:
        # TODO: template交互式添加
        if text.lower().startswith("add template"):
            args = text[len("add template ") :].strip()
            handle_add_template(args, user_id, logger, say)

        elif text.lower().startswith("list"):
            args = text[len("list ") :].strip()
            handle_list(args, user_id, logger, say)

        elif text.lower().startswith("log"):
            args = text[len("log ") :].strip()
            handle_log(args, user_id, logger, say)

        elif text.lower().startswith("test"):
            # (隐藏 测试命令) 直接回复一个不在库中的 todo Block Kit 消息
            handle_test_kit(user_id, logger, say)

        else:
            # (帮助信息)
            say(
                "*Alfred Bot 命令帮助:*\n"
                "• `/alfred add template <user_id> <name> <cron> <bias> [<run_once>]`\n"
                "  run_once 可选, 1 = 运行一次后禁用, 0 = 周期性运行, 默认为 0\n"
                "  (示例: `/alfred add template 'U0xxx' '复盘' '0 9 * * 1-5' '1h' '1'`)\n"
                "• `/alfred list [todos|templates]`\n"
                "  (默认为 `todos`)\n"
                "• `/alfred log <todo_id>`\n"
                "  (将您的待办任务标记为 'completed')"
            )
    except Exception as e:
        logger.error(f"Unhandled error in /alfred: {e}")
        say(f"An unexpected error occurred: {e}")


@app.error
def global_error_handler(error, body, logger):
    logger.error("--- Global Error ---")
    logger.error(f"Error: {error}")
    logger.error(f"Body: {body}")


@app.action("log_todo_button")
def handle_log_todo_button(ack, body, client, logger):
    """
    (新版) 监听 "Log" 按钮点击, 完成任务, 并把按钮更新为 "Undo"
    """
    # 1. 立即 ACK
    ack()

    # 2. 获取数据
    action = body["actions"][0]
    todo_id_str = action["value"]
    user_id = body["user"]["id"]

    # (关键) 获取原始消息的时间戳和 blocks
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    original_blocks = body["message"]["blocks"]

    logger.info(f"User {user_id} clicked 'log_todo_button' for todo_id {todo_id_str}")

    try:
        todo_id = int(todo_id_str)
        sim_time = datetime.now()

        # 3. (不变) 调用引擎完成任务
        engine.complete_task(todo_id, sim_time)

        # 4. (核心) 更新原始消息

        # 找到被点击的 blocks
        action_block_id = action["block_id"]  # e.g., "todo_1_actions"
        section_block_id = action_block_id.replace("_actions", "_section")

        # 从原始 blocks 中找到 task_name (用于显示 "已完成")
        task_name = f"Task {todo_id}"  # 默认
        for block in original_blocks:
            if block.get("block_id") == section_block_id:
                # 解析 "text" 字段以找到 task_name
                # (为简洁起见，我们这里硬编码一个)
                task_name_match = block["text"][
                    "text"
                ]  # e.g., "*[ID: 1]* `My Task`\n..."
                # (一个简单的解析，实际使用时应更健壮)
                try:
                    task_name = task_name_match.split("`")[1]
                except:
                    pass
                break

        # (新) 创建 "Completed" 状态的 blocks
        completed_blocks = [
            {
                "type": "section",
                "block_id": section_block_id,  # 保持 block_id 一致
                "text": {
                    "type": "mrkdwn",
                    "text": f"~*[ID: {todo_id}]* `{task_name}`~ (✅ 已完成)",
                },
            },
            {
                "type": "actions",
                "block_id": action_block_id,  # 保持 block_id 一致
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "↩️ 撤销 (Undo)"},
                        "action_id": "undo_log_button",  # <--- 新的 Action ID
                        "value": str(todo_id),
                        "style": "danger",
                    }
                ],
            },
        ]

        # 5. 在原始 blocks 列表中替换掉旧的 blocks
        new_blocks = []
        for block in original_blocks:
            if block.get("block_id") == section_block_id:
                # 这是我们要替换的 section, 先跳过
                pass
            elif block.get("block_id") == action_block_id:
                # 这是我们要替换的 actions, 把新 blocks 加进去
                new_blocks.extend(completed_blocks)
            else:
                # 这是其他 block, 保持原样
                new_blocks.append(block)

        # 6. 调用 client.chat_update
        client.chat_update(
            channel=channel_id, ts=message_ts, blocks=new_blocks, text="任务列表已更新"
        )

    except Exception as e:
        logger.error(f"Failed to log todo via button: {e}")
        # (出错时也应该通知用户)
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"❌ *记录失败*:\n`{e}`"
        )


@app.action("undo_log_button")
def handle_undo_log_button(ack, body, client, logger):
    """
    (新增) 监听 "Undo" 按钮点击, 撤销任务, 并把按钮换回 "Log"
    """
    # 1. ACK
    ack()

    # 2. 获取数据
    action = body["actions"][0]
    todo_id_str = action["value"]
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    original_blocks = body["message"]["blocks"]

    logger.info(f"User {user_id} clicked 'undo_log_button' for todo_id {todo_id_str}")

    try:
        todo_id = int(todo_id_str)
        sim_time = datetime.now()

        # 3. (核心) 调用引擎“撤销”
        # (您需要先在 TaskEngine 中实现这个 revert_task_completion)
        # (我们之前的对话中已经创建了这个函数)
        engine.revert_task_completion(todo_id, sim_time)

        # 4. (核心) 更新消息，把它换回“Pending”状态的 blocks

        # (新) 创建 "Pending" 状态的 blocks
        # (您需要一种方式从 DB 重新获取 task_name 和 status,
        #  或者从原始 block text 中解析)

        # (为简洁起见，我们假设 revert 总是回到 'pending')
        new_status = "pending"
        task_name = f"Task {todo_id}"  # (同样，这里应该从 DB 或 block 中获取)

        pending_blocks = [
            {
                "type": "section",
                "block_id": action["block_id"].replace("_actions", "_section"),
                "text": {
                    "type": "mrkdwn",
                    "text": f"*[ID: {todo_id}]* `{task_name}`\n*状态*: {new_status}",
                },
            },
            {
                "type": "actions",
                "block_id": action["block_id"],
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Log (完成)"},
                        "action_id": "log_todo_button",  # <--- 换回 "Log"
                        "value": str(todo_id),
                        "style": "primary",
                    }
                ],
            },
        ]

        # 5. 在原始 blocks 列表中替换掉 "Completed" blocks
        new_blocks = []
        for block in original_blocks:
            if block.get("block_id") == action["block_id"].replace(
                "_actions", "_section"
            ):
                pass
            elif block.get("block_id") == action["block_id"]:
                new_blocks.extend(pending_blocks)
            else:
                new_blocks.append(block)

        # 6. 调用 client.chat_update
        client.chat_update(
            channel=channel_id, ts=message_ts, blocks=new_blocks, text="任务列表已更新"
        )

    except Exception as e:
        logger.error(f"Failed to undo todo via button: {e}")
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"❌ *撤销失败*:\n`{e}`"
        )


from flask import Flask, make_response

flask_app = Flask(__name__)


@flask_app.route("/health", methods=["GET"])
def slack_events():
    if handler.client is not None and handler.client.is_connected():
        return make_response("OK", 200)
    return make_response("The Socket Mode client is inactive", 503)


@flask_app.route("/list", methods=["GET"])
def list_todos():
    todos = engine.get_todos(datetime.today().date())  # get all
    todo_list = (
        "\n".join([f"• {t[0]}" for t in todos]) if todos else "_No todos found._"
    )
    return make_response(f"*Your Project TODOs today:* \n{todo_list}", 200)


if __name__ == "__main__":
    print("Bolt app is starting...")

    # (新增) 在启动时, 调用 auth.test 获取 Bot 自己的 User ID
    try:
        # app.client 是一个预先配置好的 WebClient 实例
        auth_response = app.client.auth_test()
        # 将 Bot ID 存储在全局变量中
        BOT_USER_ID = auth_response["user_id"]
        print(f"Successfully authenticated as Bot User ID: {BOT_USER_ID}")
    except Exception as e:
        print(f"Error fetching bot user ID: {e}")
        print("Please check SLACK_BOT_TOKEN and bot permissions (auth:test scope).")
        sys.exit(1)

    # Create an app-level token with connections:write scope
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.connect()  # Keep the Socket Mode client running but non-blocking
    flask_app.run(port=8080)
