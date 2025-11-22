from datetime import datetime

from alfred.slack.app import app
from alfred.slack.butler import butler


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

    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    original_blocks = body["message"]["blocks"]
    logger.info(f"User {user_id} clicked 'log_todo_button' for todo_id {todo_id_str}")

    try:
        todo_id = int(todo_id_str)
        butler.mark_todo_complete(todo_id)
        # generate from todo id, more clear
        completed_blocks = butler.build_single_todo_blocks(todo_id)
        new_blocks = butler.replace_todo_blocks_in_message(
            original_blocks, todo_id, completed_blocks
        )

        client.chat_update(
            channel=channel_id, ts=message_ts, blocks=new_blocks, text="任务列表已更新"
        )

        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=f"✅ <@{user_id}> 于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成了任务。",
            reply_broadcast=False,  # do not notify channel, just reply in thread
        )

    except Exception as e:
        logger.exception(f"Failed to log todo via button: {e}")
        # if failed, notify user
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"❌ *记录失败*:\n`{e}`"
        )


@app.action("mark_todo_undo")
def handle_mark_todo_undo(ack, body, client, logger):
    """
    监听 "Undo" 按钮点击, 撤销任务完成状态。
    """
    ack()

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
        new_blocks = butler.replace_todo_blocks_in_message(
            original_blocks, todo_id, pending_blocks
        )

        client.chat_update(
            channel=channel_id, ts=message_ts, blocks=new_blocks, text="任务列表已更新"
        )

        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=f"↩️ <@{user_id}> 于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 撤销了任务完成状态。",
            reply_broadcast=False,
        )

    except Exception as e:
        logger.exception(f"Failed to undo todo via button: {e}")
        client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"❌ *撤销失败*:\n`{e}`"
        )
