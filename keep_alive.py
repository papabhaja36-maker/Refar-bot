import os
import threading
import logging
from flask import Flask

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route("/")
def home():
    return "Bot is alive!", 200

@app.route("/health")
def health():
    return {"status": "ok"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_flask_thread():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
