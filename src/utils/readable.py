def gen_todo_desc(task_engine, todo_id):
    """
    Generate formatted markdown text for a todo item given its ID.
    """
    todo = task_engine.get_todo(todo_id)
    if not todo:
        return f"No TODO found with ID {todo_id}."

    todo_content = todo[1]
    status = todo[4]
    remind_time = todo[2]
    ddl_time = todo[3]

    desc = (
        f"*Task:* {todo_content}\n"
        f"*Status:* {status}\n"
        f"*Reminder Time:* {remind_time}\n"
        f"*Deadline Time:* {ddl_time}\n"
    )
    return desc
