"""
main.py - Bot + Flask dono ek saath start hoga.
Render pe ye file run hoga: python main.py
"""
import threading
import logging
from keep_alive import run_flask
from bot import main as run_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Flask server alag thread mein
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask server thread start ho gaya")

    # Bot main thread mein
    logger.info("✅ Telegram bot start ho raha hai...")
    run_bot()
