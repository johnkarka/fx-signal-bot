from threading import Thread
from app import app
from bot import main as run_bot  # Should also expose `updater` if using polling
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
    print(f"\n🛑 Received signal {signum}, shutting down...")

    # Stop Telegram polling (assuming updater is imported or set globally)
    try:
        from bot import updater  # Your bot module must expose this
        if updater:
            print("📴 Stopping Telegram bot polling...")
            updater.stop()
            updater.is_idle = False  # Break idle loop
    except ImportError:
        print("⚠️ No updater object found in bot module.")

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
    # Register graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start Flask app in a background thread
    Thread(target=start_web, daemon=True).start()

    # Start tunnel
    cloudflared_proc, url = start_cloudflared_tunnel()
    if url:
        os.environ["LOCAL_TUNNEL_URL"] = url
        print(f"🌐 LOCAL_TUNNEL_URL set to: {url}")
    else:
        print("⚠️ Running bot without tunnel URL.")

    # Start Telegram bot (should block)
    run_bot()

    # No need for while loop — `run_bot()` should block.
