def format_todos(todos):
    if not todos:
        return "_No todos found._"
    todo_lines = []
    for todo in todos:
        # TODO: user id display
        line = f"- [ID: {todo['todo_id']}] <@{todo['user_id']}> {todo['content']} (Status: {todo['status']}, DDL: {todo['ddl_time']})"
        todo_lines.append(line)
    return "\n".join(todo_lines)


def format_templates(templates):
    if not templates:
        return "_No templates found._"
    template_lines = []
    for template in templates:
        line = f"- [ID: {template['template_id']}] <@{template['user_id']}> {template['content']} (Cron: {template['cron']}, Active: {template['is_active']})"
        template_lines.append(line)
    return "\n".join(template_lines)


def format_todo_logs(logs):
    if not logs:
        return "_No logs found._"
    log_lines = []
    for log in logs:
        line = f"- [Time: {log['timestamp']}] Status changed from {log['old_status']} to {log['new_status']}"
        log_lines.append(line)
    return "\n".join(log_lines)


def build_add_template_view(view_callback_id: str, current_freq: str = "weekdays"):
    """
    动态构建模态框 UI
    :param current_freq: 当前选中的频率，用于控制显示哪些字段
    """
    
    # 辅助：获取下拉菜单显示的文本
    def get_freq_label(val):
        mapping = {
            "daily": "每天 (Daily)",
            "weekdays": "工作日 (Mon-Fri)",
            "weekly": "每周 (Weekly - Mon)",
            "monthly_rule": "每月规则 (例如: 第2个周五)",
            "custom": "自定义 (Custom Cron)"
        }
        return mapping.get(val, "工作日 (Mon-Fri)")

    # --- 1. 固定头部 ---
    blocks = [
        {
            "type": "input",
            "block_id": "block_user",
            "element": {"type": "users_select", "action_id": "action_user", "placeholder": {"type": "plain_text", "text": "选择用户"}},
            "label": {"type": "plain_text", "text": "目标用户"}
        },
        {
            "type": "input",
            "block_id": "block_content",
            "element": {"type": "plain_text_input", "action_id": "action_content", "placeholder": {"type": "plain_text", "text": "任务内容"}},
            "label": {"type": "plain_text", "text": "任务内容"}
        },
        {"type": "divider"},
        
        # --- 2. 频率选择器 (核心交互点) ---
        {
            "type": "input",
            "block_id": "block_frequency",
            "dispatch_action": True, # 开启交互，选完立即触发 action
            "element": {
                "type": "static_select",
                "action_id": "action_frequency",
                "placeholder": {"type": "plain_text", "text": "选择频率"},
                "initial_option": {
                    "text": {"type": "plain_text", "text": get_freq_label(current_freq)}, 
                    "value": current_freq
                },
                "options": [
                    {"text": {"type": "plain_text", "text": "每天 (Daily)"}, "value": "daily"},
                    {"text": {"type": "plain_text", "text": "工作日 (Mon-Fri)"}, "value": "weekdays"},
                    {"text": {"type": "plain_text", "text": "每周一 (Weekly)"}, "value": "weekly"},
                    {"text": {"type": "plain_text", "text": "每月规则 (例如: 第2个周五)"}, "value": "monthly_rule"},
                    {"text": {"type": "plain_text", "text": "自定义 (Custom Cron)"}, "value": "custom"}
                ]
            },
            "label": {"type": "plain_text", "text": "重复频率"}
        }
    ]

    # --- 3. 动态字段逻辑 ---

    if current_freq == "custom":
        # === 模式 A: 自定义 Cron ===
        blocks.append({
            "type": "input",
            "block_id": "block_raw_cron",
            "element": {
                "type": "plain_text_input", 
                "action_id": "action_raw_cron", 
                "placeholder": {"type": "plain_text", "text": "0 9 * * 1-5"}
            },
            "label": {"type": "plain_text", "text": "Cron 表达式"},
            "hint": {"type": "plain_text", "text": "请输入完整的标准 Cron 表达式"}
        })
    
    else:
        # === 模式 B: 标准时间选择 ===
        blocks.append({
            "type": "input",
            "block_id": "block_time",
            "element": {
                "type": "timepicker", 
                "action_id": "action_time", 
                "initial_time": "09:30", 
                "placeholder": {"type": "plain_text", "text": "选择时间"}
            },
            "label": {"type": "plain_text", "text": "提醒时间"}
        })

        # === 模式 C: 每月规则额外字段 ===
        if current_freq == "monthly_rule":
            # 这里使用了两个并排的 Input (UI上是上下排)，用来拼凑 "FRI#2"
            blocks.append({
                "type": "input",
                "block_id": "block_month_week",
                "element": {
                    "type": "static_select",
                    "action_id": "action_month_week",
                    "placeholder": {"type": "plain_text", "text": "第几个?"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "第 1 个"}, "value": "1"},
                        {"text": {"type": "plain_text", "text": "第 2 个"}, "value": "2"},
                        {"text": {"type": "plain_text", "text": "第 3 个"}, "value": "3"},
                        {"text": {"type": "plain_text", "text": "第 4 个"}, "value": "4"},
                        # Croniter 支持 #5，如果该月没第5个则不运行，逻辑是通的
                        {"text": {"type": "plain_text", "text": "第 5 个"}, "value": "5"} 
                    ]
                },
                "label": {"type": "plain_text", "text": "规则: 第几周"}
            })
            blocks.append({
                "type": "input",
                "block_id": "block_month_day",
                "element": {
                    "type": "static_select",
                    "action_id": "action_month_day",
                    "placeholder": {"type": "plain_text", "text": "周几?"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "周一 (Mon)"}, "value": "MON"},
                        {"text": {"type": "plain_text", "text": "周二 (Tue)"}, "value": "TUE"},
                        {"text": {"type": "plain_text", "text": "周三 (Wed)"}, "value": "WED"},
                        {"text": {"type": "plain_text", "text": "周四 (Thu)"}, "value": "THU"},
                        {"text": {"type": "plain_text", "text": "周五 (Fri)"}, "value": "FRI"},
                        {"text": {"type": "plain_text", "text": "周六 (Sat)"}, "value": "SAT"},
                        {"text": {"type": "plain_text", "text": "周日 (Sun)"}, "value": "SUN"}
                    ]
                },
                "label": {"type": "plain_text", "text": "规则: 周几"}
            })

    # --- 4. 固定底部 ---
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "input",
        "block_id": "block_offset",
        "element": {"type": "plain_text_input", "action_id": "action_offset", "initial_value": "1h"},
        "label": {"type": "plain_text", "text": "逾期判定 (Offset)"}
    })
    blocks.append({
        "type": "input",
        "block_id": "block_run_once",
        "element": {
            "type": "radio_buttons",
            "action_id": "action_run_once",
            "initial_option": {"text": {"type": "plain_text", "text": "周期循环"}, "value": "0"},
            "options": [
                {"text": {"type": "plain_text", "text": "周期循环"}, "value": "0"},
                {"text": {"type": "plain_text", "text": "仅一次"}, "value": "1"}
            ]
        },
        "label": {"type": "plain_text", "text": "任务类型"}
    })

    return {
        "type": "modal",
        "callback_id": view_callback_id,
        "title": {"type": "plain_text", "text": "添加定时任务"},
        "submit": {"type": "plain_text", "text": "保存"},
        "close": {"type": "plain_text", "text": "取消"},
        "blocks": blocks
    }