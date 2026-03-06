import os
import requests


BOT_TOKEN = os.getenv("BOT1_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")


def send_message(text):

    if not BOT_TOKEN or not GROUP_ID:
        print("Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": GROUP_ID,
        "text": text
    }

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Telegram error:", e)


# função usada pelo app.py
def init_telegram(app):
    print("Telegram bot initialized")