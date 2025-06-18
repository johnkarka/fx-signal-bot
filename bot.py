from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import json
import logging
import os

# Global variables to be initialized later
TOKEN = None
BOT_WEB_APP_URL = None
updater = None

def init():
    global TOKEN, BOT_WEB_APP_URL, updater

    # Logging
    logging.basicConfig(level=logging.INFO)

    # Load environment variables
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("TG_BOT_TOKEN1"))

    local_url = os.getenv("LOCAL_TUNNEL_URL")  # e.g. ngrok or cloudflare tunnel
    web_url = os.getenv("WEB_APP_URL", "https://afx-signal-bot-production.up.railway.app")
    BOT_WEB_APP_URL = local_url if local_url else web_url

    print(f"[init] Using Web App URL: {BOT_WEB_APP_URL}")

    # Create updater
    updater = Updater(TOKEN, use_context=True)

def start(update: Update, context: CallbackContext):
    button = InlineKeyboardButton("Create Strategy", web_app={"url": BOT_WEB_APP_URL})
    markup = InlineKeyboardMarkup([[button]])
    update.message.reply_text("Click to open the strategy form:", reply_markup=markup)

def handle_web_app_data(update: Update, context: CallbackContext):
    if update.message.web_app_data:
        try:
            data = json.loads(update.message.web_app_data.data)
            text = (
                f"✅ Strategy Received:\n"
                f"• Period: {data.get('period')}\n"
                f"• Compare to: {data.get('compare_to')}\n"
                f"• Threshold: {data.get('threshold')}"
            )
            update.message.reply_text(text)
        except Exception as e:
            update.message.reply_text("❌ Error processing strategy.")
            logging.error(f"[Error] {e}")

def main():
    init()  # Initialize everything

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & Filters.all, handle_web_app_data))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
