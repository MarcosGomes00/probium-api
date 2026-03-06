import requests
from config import Config


BOT_TOKEN = Config.TELEGRAM_BOT_1
CHAT_ID = Config.TELEGRAM_CHAT_ID


def send_bet_message(text):

    if not BOT_TOKEN:
        print("⚠ Telegram não configurado")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:

        r = requests.post(url, data=payload, timeout=10)

        if r.status_code == 200:
            print("📤 Mensagem enviada Telegram")
        else:
            print("Erro Telegram:", r.text)

    except Exception as e:

        print("Erro Telegram:", e)