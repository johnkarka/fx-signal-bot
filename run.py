from threading import Thread
from app import app
from bot import main as run_bot  # your Telegram bot main function
import subprocess
import shutil
import re
import time
import os
import signal
import sys

cloudflared_proc = None

def start_web():
    app.run(host="0.0.0.0", port=8001)

def start_cloudflared_tunnel():
    if not shutil.which("cloudflared"):
        print("⚠️  cloudflared not found, skipping tunnel creation.")
        return None, None

    print("🚀 Starting Cloudflare Tunnel...")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    tunnel_url = None
    for _ in range(30):
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
        print("❌ Could not find tunnel URL")
    else:
        print(f"✅ Tunnel URL found: {tunnel_url}")

    return proc, tunnel_url

def shutdown_handler(signum, frame):
    print(f"\n⚠️ Received signal {signum}, shutting down...")

    # If your run_bot returns an object with stop(), call it here.
    # For example, if run_bot starts polling, you should expose a stop method.
    # Assuming run_bot sets a global updater variable:
    try:
        from bot import updater  # example: you have updater in your bot module
        if updater:
            print("Stopping Telegram bot polling...")
            updater.stop()
            updater.is_idle = False  # To unblock idle if used
    except ImportError:
        print("No updater found in bot module, skipping bot stop.")

    global cloudflared_proc
    if cloudflared_proc and cloudflared_proc.poll() is None:
        print("Terminating Cloudflared tunnel...")
        cloudflared_proc.terminate()
        try:
            cloudflared_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Cloudflared tunnel did not terminate, killing...")
            cloudflared_proc.kill()

    print("Exiting now.")
    sys.exit(0)

if __name__ == "__main__":
    # Register shutdown signals
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start Flask in a daemon thread
    Thread(target=start_web, daemon=True).start()

    # Start cloudflared tunnel if possible
    cloudflared_proc, url = start_cloudflared_tunnel()

    if url:
        os.environ["LOCAL_TUNNEL_URL"] = url
        print(f"🌐 LOCAL_TUNNEL_URL set: {url}")
    else:
        print("🟡 Running bot without Cloudflare tunnel.")

    # Run your Telegram bot main function (assumed blocking)
    run_bot()

    # Keep the main thread alive if needed (depends on your bot implementation)
    while True:
        time.sleep(5)
