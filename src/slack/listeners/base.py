from app import app

@app.error
def global_error_handler(error, body, logger):
    logger.error("--- Global Error ---")
    logger.error(f"Error: {error}")
    logger.error(f"Body: {body}")
    logger.error("--------------------")
