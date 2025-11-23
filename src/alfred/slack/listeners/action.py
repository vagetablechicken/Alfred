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

    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_add_template_view("submit_cron_template"),
    )


@app.action("action_frequency")
def handle_frequency_update(ack, body, client):
    ack()

    # 1. 拿到用户选的新频率 (比如选了 monthly_rule)
    selected_option = body["actions"][0]["selected_option"]
    new_freq = selected_option["value"]

    view_id = body["view"]["id"]

    # 2. 传入新频率，重建 UI
    new_view = build_add_template_view(
        view_callback_id="submit_cron_template", current_freq=new_freq
    )

    # 3. 刷新
    client.views_update(view_id=view_id, view=new_view)


@app.view("submit_cron_template")
def handle_cron_submission(ack, body, view, client, logger):
    values = view["state"]["values"]
    errors = {}

    # --- 1. 提取基础数据 ---
    try:
        user_id = values["block_user"]["action_user"]["selected_user"]
        content = values["block_content"]["action_content"]["value"]
        offset = values["block_offset"]["action_offset"]["value"]
        run_once = values["block_run_once"]["action_run_once"]["selected_option"][
            "value"
        ]

        # 获取频率类型
        freq = values["block_frequency"]["action_frequency"]["selected_option"]["value"]
    except KeyError:
        # 防御性编程
        logger.error("Missing basic fields")
        return

    # --- 2. Cron 生成逻辑 ---
    final_cron = ""

    if freq == "custom":
        # 模式 A: 自定义
        raw_cron = values["block_raw_cron"]["action_raw_cron"]["value"]
        if not raw_cron:
            errors["block_raw_cron"] = "请输入 Cron 表达式"
        else:
            final_cron = raw_cron

    else:
        # 模式 B: 需要处理时间
        time_str = values["block_time"]["action_time"]["selected_time"]
        if not time_str:
            errors["block_time"] = "请选择时间"
            ack(response_action="errors", errors=errors)
            return

        hour, minute = time_str.split(":")

        if freq == "daily":
            # 每天: mm HH * * *
            final_cron = f"{minute} {hour} * * *"

        elif freq == "weekdays":
            # 工作日: mm HH * * 1-5
            final_cron = f"{minute} {hour} * * 1-5"

        elif freq == "weekly":
            # 每周一: mm HH * * 1 (你可以改为让用户选，这里简化为周一)
            final_cron = f"{minute} {hour} * * 1"

        elif freq == "monthly_rule":
            # === 核心：处理 FRI#2 语法 ===
            selected_week = values["block_month_week"]["action_month_week"][
                "selected_option"
            ]
            selected_day = values["block_month_day"]["action_month_day"][
                "selected_option"
            ]

            if not selected_week:
                errors["block_month_week"] = "请选择第几周"
            if not selected_day:
                errors["block_month_day"] = "请选择周几"

            if errors:
                ack(response_action="errors", errors=errors)
                return

            week_val = selected_week["value"]  # e.g., "2"
            day_val = selected_day["value"]  # e.g., "FRI"

            # 生成 croniter 支持的格式: 分 时 * * 周几#第几
            # 结果: 30 09 * * FRI#2
            final_cron = f"{minute} {hour} * * {day_val}#{week_val}"

    # --- 3. 错误处理与保存 ---
    if errors:
        ack(response_action="errors", errors=errors)
        return

    # 验证通过，关闭弹窗
    ack()

    logger.info(
        f"Adding cron template: user_id={user_id}, content={content}, cron={final_cron}, offset={offset}, run_once={run_once}"
    )

    # Send confirmation (Async)
    try:
        template_id = butler.add_template(
            user_id=user_id,
            content=content,
            cron=final_cron,
            ddl_offset=offset,
            run_once=run_once,
        )
        logger.info(f"Successfully added cron template ID {template_id}")
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=(
                f"✅ 已为 <@{user_id}> 添加定时任务模板 *{content}*，"
                f"模板ID: {template_id}。"
            ),
        )
    except Exception as e:
        logger.error(f"Failed to notify: {e}")
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"❌ 添加定时任务模板失败:\n`{e}`",
        )
