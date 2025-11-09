from app import app

# I don't care about normal messages, you can remove the event subscription if you want
# Just a protective handler
@app.event("message")
def handle_all_messages(message, say, logger):
    user_id = message.get("user")
    text = message.get("text", "")
    channel_id = message.get("channel")
    logger.info(f"Received a message from <@{user_id}> in channel {channel_id}: {text}")
    if message.get("bot_id") is not None:
        logger.debug("Ignoring message from a bot (or itself)")
        return
    logger.debug("No action taken for this message.")
