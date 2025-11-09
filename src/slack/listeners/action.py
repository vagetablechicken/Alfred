from datetime import datetime

from ..app import app
from ...task.task_engine import task_engine
from ...utils.readable import gen_todo_desc


@app.action("log_todo_button")
def handle_log_todo_button(ack, body, client, logger):
    """
    Handle action_id "log_todo_button".
    If the user clicks the button, mark the todo as completed
    """
    ack()

    action = body["actions"][0]
    todo_id_str = action["value"]
    user_id = body["user"]["id"]

    # 获取原始消息的时间戳和 blocks
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    original_blocks = body["message"]["blocks"]

    logger.info(f"User {user_id} clicked 'log_todo_button' for todo_id {todo_id_str}")

    try:
        todo_id = int(todo_id_str)
        sim_time = datetime.now()

        task_engine.complete_task(todo_id, sim_time)

        # update the message to reflect the completed status

        # find the relevant blocks to update
        action_block_id = action["block_id"]  # e.g., "todo_1_actions"
        section_block_id = action_block_id.replace("_actions", "_section")

        # generate from task id, more clear
        task_text = gen_todo_desc(task_engine, todo_id)

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
