import requests
from config import Config


def send_bet_message(text):

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_1}/sendMessage"

    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": text
    }

    requests.post(url, data=payload)


def send_report_message(text):

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_2}/sendMessage"

    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": text
    }

    requests.post(url, data=payload)