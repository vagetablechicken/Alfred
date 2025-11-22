
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
        line = f"- [ID: {template['template_id']}] {template['todo_content']} (Cron: {template['cron']}, Active: {template['is_active']})"
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
