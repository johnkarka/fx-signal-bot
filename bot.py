from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import json
import logging
import os
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN",os.getenv("TG_BOT_TOKEN1"))
WEB_APP_URL = os.getenv("TELEGRAM_BOT_TOKEN","fx-signal-bot-production.up.railway.app")  # ← Update this after starting ngrok

logging.basicConfig(level=logging.INFO)

def start(update: Update, context: CallbackContext):
    button = InlineKeyboardButton(
        "Create Strategy", web_app={"url": WEB_APP_URL}
    )
    markup = InlineKeyboardMarkup([[button]])
    update.message.reply_text("Click to open the strategy form:", reply_markup=markup)

def handle_web_app_data(update: Update, context: CallbackContext):
    data = json.loads(update.message.web_app_data.data)
    text = (
        f"Strategy Received:\n"
        f"Period: {data.get('period')}\n"
        f"Compare to: {data.get('compare_to')}\n"
        f"Threshold: {data.get('threshold')}"
    )
    update.message.reply_text(text)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(
        Filters.text & Filters.all,  # this allows all text
        lambda update, context: handle_web_app_data(update, context)
    ))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
