import asyncio
import logging
from threading import Thread
from bot import main as run_bot  # async function that runs your Telegram bot
import subprocess
import shutil
import re
import time
import os
import signal
import sys
import pytz
import nest_asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app import create_app

nest_asyncio.apply()
logging.basicConfig(level=logging.DEBUG)
app = create_app()
cloudflared_proc = None

def is_tunnel_running():
    """Check if an existing tunnel is running via LOCAL_TUNNEL_URL."""
    url = os.getenv("LOCAL_TUNNEL_URL")
    if not url:
        return False
    try:
        r = requests.get(url, timeout=2)
        return r.status_code < 500
    except Exception:
        return False

def start_web():
    """Start the Flask web app."""
    app.run(host="0.0.0.0", port=8001)

def start_cloudflared_tunnel():
    """Start or reuse a Cloudflare tunnel to expose localhost:8001."""
    if not shutil.which("cloudflared"):
        print("⚠️  cloudflared not found, skipping tunnel creation.")
        return None, None

    if is_tunnel_running():
        print("✅ Existing Cloudflare Tunnel is running, skipping new tunnel start.")
        return None, os.getenv("LOCAL_TUNNEL_URL")

    print("🚀 Starting Cloudflare Tunnel...")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    tunnel_url = None
    for _ in range(60):  # wait up to 30 seconds
        if proc.poll() is not None:
            print("❌ cloudflared process exited prematurely.")
            break
        line = proc.stdout.readline()
        if not line:
            continue
        print("[cloudflared]", line.strip())
        match = re.search(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            break
        time.sleep(0.5)

    if tunnel_url:
        print(f"✅ Tunnel URL found: {tunnel_url}")
        # Optional: Save to .env file for external tools
        # with open(".env", "a") as f:
        #     f.write(f"LOCAL_TUNNEL_URL={tunnel_url}\n")
    else:
        print("❌ Could not extract tunnel URL from cloudflared output.")

    return proc, tunnel_url

def shutdown_handler(signum, frame):
    """Handle graceful shutdown and cleanup."""
    print(f"\n🛑 Received signal {signum}, shutting down...")

    global cloudflared_proc
    if cloudflared_proc and cloudflared_proc.poll() is None:
        print("🛑 Terminating Cloudflare tunnel...")
        cloudflared_proc.terminate()
        try:
            cloudflared_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️ Cloudflare tunnel not exiting, killing...")
            cloudflared_proc.kill()

    print("✅ Clean shutdown complete.")
    sys.exit(0)

if __name__ == "__main__":
    AsyncIOScheduler.timezone = pytz.utc  # change to pytz.timezone("Asia/Yangon") if needed
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start Flask in a background thread
    Thread(target=start_web, daemon=True).start()

    # Start or reuse tunnel
    cloudflared_proc, url = start_cloudflared_tunnel()
    if url:
        os.environ["LOCAL_TUNNEL_URL"] = url
        print(f"🌐 LOCAL_TUNNEL_URL set to: {url}")
    else:
        print("⚠️ Running bot without tunnel URL.")

    # Start the Telegram bot
    asyncio.run(run_bot())