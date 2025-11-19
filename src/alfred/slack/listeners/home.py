from datetime import datetime
from alfred.slack.app import app


@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    user_id = event["user"]
    today = datetime.now().date().strftime("%Y年%m月%d日")

    # 1. 获取用户名
    try:
        user_info = client.users_info(user=user_id)
        # 优先使用 display_name (昵称)，如果没有则用 real_name (全名)
        user_name = user_info["user"]["profile"].get("display_name") or user_info[
            "user"
        ].get("real_name")
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        user_name = "用户"  # 兜底称呼

    try:
        client.views_publish(
            user_id=user_id,
            view=generate_home_view(today, user_name),
        )
    except Exception as e:
        logger.error(f"Error publishing home tab: {e}")


def generate_home_view(today, user_name):
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"👋 您好，{user_name}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"📅 {today} | 🤖 我已就绪"}],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*我是您的团队任务助手。*\n\n为了保持界面清爽, 我不在这里展示列表。请直接在 *Messages(消息页)* 发送指令给我，我会帮您记录一切。",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "暂时不支持在此页面操作, 以及交互创建任务, 敬请期待更多功能！",
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "需要帮助？随时输入 `/alfred help`。",
                    }
                ],
            },
        ],
    }
