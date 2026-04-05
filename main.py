import os
import logging
from keep_alive import start_flask_thread
from bot import main as run_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    start_flask_thread()
    logger.info("✅ Flask thread started")
    run_bot()
