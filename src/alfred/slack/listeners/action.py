from datetime import datetime

from ..app import app
from ..butler import butler


@app.action("mark_todo_complete")
def handle_mark_todo_complete(ack, body, client, logger):
    """
    Handle action_id "mark_todo_complete".
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
        butler.mark_todo_complete(todo_id)

        # update the message to reflect the completed status

        # find the relevant blocks to update
        action_block_id = action["block_id"]  # e.g., "todo_1_actions"
        section_block_id = action_block_id.replace("_actions", "_section")

        # generate from todo id, more clear
        completed_blocks = butler.build_single_todo_blocks(todo_id)

        # TODO: 替换有问题
        new_blocks = []
        for block in original_blocks:
            # TODO: 依赖顺序可能不太好，考虑用 block_id 来匹配
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
        logger.exception(f"Failed to log todo via button")
        # (出错时也应该通知用户)
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"❌ *记录失败*:\n`{e}`"
        )


@app.action("mark_todo_undo")
def handle_mark_todo_undo(ack, body, client, logger):
    """
    监听 "Undo" 按钮点击, 撤销任务完成状态。
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

        butler.mark_todo_undo(todo_id)
        pending_blocks = butler.build_single_todo_blocks(todo_id)

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
