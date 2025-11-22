from datetime import datetime
from alfred.slack.app import app


@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    user_id = event["user"]
    today = datetime.now().date().strftime("%Y-%m-%d")

    # 1. Get username
    try:
        user_info = client.users_info(user=user_id)
        # Prefer display_name (nickname), fallback to real_name (full name)
        user_name = user_info["user"]["profile"].get("display_name") or user_info[
            "user"
        ].get("real_name")
    except Exception as e:
        logger.error(f"Failed to fetch user info: {e}")
        user_name = "User"  # Fallback name

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
                "text": {"type": "plain_text", "text": f"👋 Hello, {user_name}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"📅 {today} | 🤖 Ready"}],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*I'm your team task assistant.*\n\nTo keep the interface clean, I don't show lists here. Please send commands directly in *Messages* and I'll help you track everything.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Interactive task creation is not yet supported on this page. Stay tuned for more features!",
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Need help? Type `/alfred help` anytime.",
                    }
                ],
            },
        ],
    }
