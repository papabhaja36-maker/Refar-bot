"""
Flask server - Render pe bot ko sleep hone se bachata hai.
UptimeRobot ya koi bhi ping service se is URL ko ping karo.
"""
from flask import Flask
import threading
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.route("/")
def home():
    return "✅ Bot is alive!", 200


@app.route("/health")
def health():
    return {"status": "ok", "bot": "running"}, 200


def run_flask():
    """Flask ko alag thread mein chalao."""
    port = 8080
    logger.info(f"Flask server port {port} pe chal raha hai...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start_flask_thread():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
