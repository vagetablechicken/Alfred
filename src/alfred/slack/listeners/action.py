from datetime import datetime

from alfred.slack.app import app
from alfred.slack.butler import butler
from alfred.utils.format import build_add_template_view


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


@app.action("open_add_template_modal")
def open_add_template_modal(ack, body, client):
    ack()

    client.views_open(trigger_id=body["trigger_id"], view=build_add_template_view(view="submit_cron_template"))


@app.view("submit_cron_template")
def handle_cron_submission(ack, body, view, logger, client):
    # 1. 提取 values 字典
    state_values = view["state"]["values"]

    # 2. 提取各个字段的数据
    # 提取 User ID (注意字段名是 selected_user)
    target_user_id = state_values["block_user"]["action_user"]["selected_user"]

    # 提取 Name
    task_name = state_values["block_name"]["action_name"]["value"]

    # 提取 Cron
    cron_exp = state_values["block_cron"]["action_cron"]["value"]

    # 提取 Offset
    offset_val = state_values["block_offset"]["action_offset"]["value"]

    # 提取 Run Once (注意处理 radio button)
    selected_run_option = state_values["block_run_once"]["action_run_once"][
        "selected_option"
    ]
    # 如果 UI 有 default 选项，这里通常不会为空，但为了安全可以加默认值
    run_once_val = selected_run_option["value"] if selected_run_option else "0"

    # 3. 简单的后端校验 (可选)
    # 比如校验 offset 格式是否正确
    if not offset_val.endswith(("h", "m", "s")):
        ack(
            response_action="errors",
            errors={
                "block_offset": "Offset 格式错误，必须以 h, m, 或 s 结尾 (例如 1h)"
            },
        )
        return

    # 4. 校验通过，关闭弹窗
    ack()

    logger.info(
        f"Added new cron template: User={target_user_id}, Name={task_name}, "
        f"Cron={cron_exp}, Offset={offset_val}, RunOnce={run_once_val}"
    )
    try:
        template_id = butler.add_template(
            user_id=target_user_id,
            todo_content=task_name,
            cron=cron_exp,
            offset=offset_val,
            run_once=int(run_once_val),
        )
        logger.info(f"Successfully added cron template ID {template_id}")
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=(
                f"✅ 已为 <@{target_user_id}> 添加定时任务模板 *{task_name}*，"
                f"模板ID: {template_id}。"
            ),
        )
    except Exception as e:
        logger.error(f"Error adding cron template: {e}")
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"❌ 添加定时任务模板失败:\n`{e}`",
        )
