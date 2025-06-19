import os
import json
import logging
import requests
from urllib.parse import urljoin
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import nest_asyncio
import asyncio
import signal

nest_asyncio.apply()

DATA_DIR = "data"
STATS_FILE = "stats.json"
FORM_PATH = "form-test"
stats = {}

def load_stats():
    stats_file = os.path.join(DATA_DIR, STATS_FILE)
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            return json.load(f)
    return {}

def save_stats():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    stats_file = os.path.join(DATA_DIR, STATS_FILE)
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=4)
    print(f"[save_stats] Stats saved: {stats}")

def set_menu_button(token, web_app_url):
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "📈 Strategy",
            "web_app": {"url": web_app_url},
        }
    }
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/setChatMenuButton", json=payload
    )
    if resp.ok:
        logging.info(f"✅ Menu button set: {resp.json()}")
    else:
        logging.error(f"❌ Failed to set menu button: {resp.text}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats["start_count"] = stats.get("start_count", 0) + 1
    save_stats()

    form_url = context.bot_data["FORM_PATH"]
    button = InlineKeyboardButton(text="Open Mini App", web_app=WebAppInfo(url=form_url))
    keyboard = InlineKeyboardMarkup([[button]])
    await update.message.reply_text("Click to open Mini App:", reply_markup=keyboard)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.web_app_data:
        try:
            data = json.loads(update.message.web_app_data.data)
            stats["web_app_data_count"] = stats.get("web_app_data_count", 0) + 1
            save_stats()

            msg = (
                f"✅ Strategy Received:\n"
                f"• Period: {data.get('period')}\n"
                f"• Compare to: {data.get('compare_to')}\n"
                f"• Threshold: {data.get('threshold')}"
            )
            await update.message.reply_text(msg)
        except Exception as e:
            logging.error(f"[Error parsing web app data] {e}")
            await update.message.reply_text("❌ Error processing strategy.")

async def main():
    logging.basicConfig(level=logging.INFO)
    global stats
    stats = load_stats()

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("TG_BOT_TOKEN1"))
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN is missing.")

    local_url = os.getenv("LOCAL_TUNNEL_URL")
    web_url = os.getenv("WEB_APP_URL") or "https://afx-signal-bot-production.up.railway.app"
    web_app_url = local_url if local_url else web_url
    form_url = urljoin(web_app_url, FORM_PATH)

    print(f"[init] Using Web App URL: {web_app_url}")
    print(f"[init] Form path set to: {form_url}")
    set_menu_button(TOKEN, web_app_url)

    app = ApplicationBuilder().token(TOKEN).build()
    app.bot_data["FORM_PATH"] = form_url

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    # Run polling; this manages starting and stopping internally.
    await app.run_polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Graceful shutdown handler
    def shutdown():
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        logging.info("Bot shutdown gracefully")
    finally:
        loop.close()