from threading import Thread
from app import app
from bot import main as run_bot  # your Telegram bot main function
import subprocess
import shutil
import re
import time
import os

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

if __name__ == "__main__":
    Thread(target=start_web, daemon=True).start()

    # Try starting cloudflared tunnel
    cloudflared_proc, url = start_cloudflared_tunnel()

    if url:
        os.environ["LOCAL_TUNNEL_URL"] = url
        print(f"🌐 LOCAL_TUNNEL_URL set: {url}")
    else:
        print("🟡 Running bot without Cloudflare tunnel.")

    run_bot()

    while True:
        time.sleep(5)
