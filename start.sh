#!/bin/bash

# Start the Telegram bot in the background
python bot.py &

# Start the Flask app in the foreground (keeps container alive)
python app.py
