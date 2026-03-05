import requests
import os

BOT_TOKEN = os.getenv("8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A")
GROUP_ID = os.getenv("-1003814625223")

def send_message(text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": GROUP_ID,
        "text": text
    }

    requests.post(url, json=payload)