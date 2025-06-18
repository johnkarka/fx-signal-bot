# run.py

from threading import Thread
from app import app
from bot import main as run_bot  # your Telegram bot main function
import subprocess
import re
import time
import os

def start_web():
    app.run(host="0.0.0.0", port=8001)

def start_cloudflared_tunnel():
    # Start cloudflared as a subprocess
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    tunnel_url = None
    # Wait and read output lines to find URL
    for _ in range(30):  # check 30 lines max, adjust if needed
        line = proc.stdout.readline()
        if not line:
            break
        print("[cloudflared]", line.strip())
        match = re.search(r"https://[a-zA-Z0-9.-]*\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            break
        time.sleep(0.5)

    if tunnel_url is None:
        print("Could not find tunnel URL")
    else:
        print(f"Tunnel URL found: {tunnel_url}")

    return proc, tunnel_url

if __name__ == "__main__":
    # Start your web server in a daemon thread
    Thread(target=start_web, daemon=True).start()

    # Start cloudflared tunnel and capture URL
    cloudflared_proc, url = start_cloudflared_tunnel()

    if url is None:
        print("Exiting: no tunnel URL available")
        exit(1)

    # Option 1: set environment variable for your bot to read
    os.environ["LOCAL_TUNNEL_URL"] = url
    print(f"LOCAL_TUNNEL_URL:{url}")

    # Option 2: pass url as argument to your bot main function (if you refactor it)
    # run_bot(url)

    # Now run your bot, which can read os.environ["TUNNEL_URL"]
    run_bot()

    # Optional: keep main thread alive if needed
    while True:
        time.sleep(5)
