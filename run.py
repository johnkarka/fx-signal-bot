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

def load_cached_tunnel_url():
    if not os.getenv("LOCAL_TUNNEL_URL") and os.path.exists(".last_tunnel_url"):
        with open(".last_tunnel_url") as f:
            cached_url = f.read().strip()
            os.environ["LOCAL_TUNNEL_URL"] = cached_url
            print(f"🔄 Recovered cached tunnel URL: {cached_url}")

def start_web():
    """Start the Flask web app."""
    app.run(host="0.0.0.0", port=8001)

def start_cloudflared_tunnel(max_retries=1):
    """Start or reuse a free Cloudflare tunnel and return its URL."""
    if not shutil.which("cloudflared"):
        print("⚠️  cloudflared not found, skipping tunnel creation.")
        return os.getenv("LOCAL_TUNNEL_URL")

    if is_tunnel_running():
        print("✅ Reusing existing Cloudflare Tunnel.")
        return os.getenv("LOCAL_TUNNEL_URL")

    for attempt in range(max_retries):
        print(f"🚀 Starting Cloudflare Tunnel... (attempt {attempt + 1})")
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,  # Fully detached process
        )

        tunnel_url = None
        for _ in range(60):  # wait up to 30 seconds
            if proc.poll() is not None:
                print("❌ cloudflared exited too early.")
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
            os.environ["LOCAL_TUNNEL_URL"] = tunnel_url
            with open(".last_tunnel_url", "w") as f:
                f.write(tunnel_url)
            return tunnel_url
        else:
            print("❌ Could not extract tunnel URL.")

        print("⏳ Waiting 10 seconds before retry...")
        time.sleep(10)

    print("❌ All attempts to start cloudflared failed.")
    return None

def shutdown_handler(signum, frame):
    """Graceful shutdown without killing cloudflared."""
    print(f"\n🛑 Received signal {signum}, shutting down app (tunnel remains alive).")
    print("✅ App shutdown complete.")
    sys.exit(0)

if __name__ == "__main__":
    AsyncIOScheduler.timezone = pytz.utc  # change if needed
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    load_cached_tunnel_url()  # restore tunnel URL if exists

    Thread(target=start_web, daemon=True).start()  # Start Flask

    url = start_cloudflared_tunnel()
    if url:
        print(f"🌐 LOCAL_TUNNEL_URL set to: {url}")
    else:
        print("⚠️ Running bot without tunnel URL.")

    asyncio.run(run_bot())