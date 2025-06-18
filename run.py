# run.py

from threading import Thread
from app import app
from bot import main as run_bot  # this includes updater.idle()

def start_web():
    app.run(host="0.0.0.0", port=8001)

if __name__ == "__main__":
    # Start web app in background thread
    #Thread(target=start_web, daemon=True).start()

    # Run Telegram bot in main thread (to allow signals)
    run_bot()
    #app.run(host="0.0.0.0", port=8000)
    pass
