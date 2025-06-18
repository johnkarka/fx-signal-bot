# run.py

import threading
from app import app
from bot import main as run_bot

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8000)
