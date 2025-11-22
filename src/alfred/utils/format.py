def format_todos(todos):
    if not todos:
        return "_No todos found._"
    todo_lines = []
    for todo in todos:
        line = f"- [ID: {todo['todo_id']}] {todo['content']} (Status: {todo['status']}, DDL: {todo['ddl_time']})"
        todo_lines.append(line)
    return "\n".join(todo_lines)


def format_templates(templates):
    if not templates:
        return "_No templates found._"
    template_lines = []
    for template in templates:
        line = f"- [ID: {template['template_id']}] {template['content']} (Cron: {template['cron']}, Active: {template['is_active']})"
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


def build_add_template_view(view: str):
    return {
        "type": "modal",
        "callback_id": view,  # bind on submission view handler
        "title": {"type": "plain_text", "text": "添加定时任务模版"},
        "submit": {"type": "plain_text", "text": "保存"},
        "close": {"type": "plain_text", "text": "取消"},
        "blocks": [
            # 1. User ID (使用选择器，而非手输 U0xxx)
            {
                "type": "input",
                "block_id": "block_user",
                "element": {
                    "type": "users_select",
                    "action_id": "action_user",
                    "placeholder": {"type": "plain_text", "text": "选择目标用户"},
                },
                "label": {"type": "plain_text", "text": "目标用户 (User)"},
            },
            # 2. Content
            {
                "type": "input",
                "block_id": "block_content",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "action_content",
                    "placeholder": {"type": "plain_text", "text": "例如: Review提醒"},
                },
                "label": {"type": "plain_text", "text": "任务内容 (Content)"},
            },
            # 3. Cron 表达式
            {
                "type": "input",
                "block_id": "block_cron",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "action_cron",
                    "placeholder": {"type": "plain_text", "text": "0 9 * * 1-5"},
                    "action_id": "action_cron",
                },
                "label": {"type": "plain_text", "text": "Cron 表达式"},
                "hint": {
                    "type": "plain_text",
                    "text": "格式: 分 时 日 月 周 (例如: 工作日早上9点)",
                },
            },
            # 4. Offset
            {
                "type": "input",
                "block_id": "block_offset",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "action_offset",
                    "placeholder": {"type": "plain_text", "text": "例如: 1h"},
                },
                "label": {"type": "plain_text", "text": "逾期偏移 (Offset)"},
                "hint": {"type": "plain_text", "text": "例如: 1h, 30m"},
            },
            # 5. Run Once (单选按钮，默认选0)
            {
                "type": "input",
                "block_id": "block_run_once",
                "element": {
                    "type": "radio_buttons",
                    "action_id": "action_run_once",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "周期执行 (默认)"},
                            "value": "0",
                        },
                        {
                            "text": {"type": "plain_text", "text": "仅执行一次"},
                            "value": "1",
                        },
                    ],
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "周期执行 (默认)"},
                        "value": "0",
                    },
                },
                "label": {"type": "plain_text", "text": "执行方式 (Run Once)"},
            },
        ],
    }
