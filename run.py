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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import nest_asyncio
nest_asyncio.apply()
from app import create_app

app = create_app()
cloudflared_proc = None
logging.basicConfig(level=logging.DEBUG)

def is_tunnel_running():
    # Simple check: If LOCAL_TUNNEL_URL env var set and URL is reachable, assume tunnel running
    url = os.getenv("LOCAL_TUNNEL_URL")
    if not url:
        return False
    try:
        import requests
        r = requests.get(url, timeout=2)
        return r.status_code < 500
    except Exception:
        return False

def start_web():
    app.run(host="0.0.0.0", port=8001)

def start_cloudflared_tunnel():
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
    AsyncIOScheduler.timezone = pytz.utc  # or pytz.timezone("Asia/Yangon")
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    Thread(target=start_web, daemon=True).start()

    cloudflared_proc, url = start_cloudflared_tunnel()
    if url:
        os.environ["LOCAL_TUNNEL_URL"] = url
        print(f"🌐 LOCAL_TUNNEL_URL set to: {url}")
    else:
        print("⚠️ Running bot without tunnel URL.")

    asyncio.run(run_bot())