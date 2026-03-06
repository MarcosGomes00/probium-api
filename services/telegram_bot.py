import requests
import os


BOT_TOKEN = os.getenv("BOT1_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_GROUP_ID")


def init_telegram(app):
    print("🤖 Telegram bot initialized")


def send_bet_message(text):

    if not BOT_TOKEN or not CHAT_ID:
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
            print("📤 Mensagem enviada no Telegram")

        else:
            print("❌ erro telegram", r.text)

    except Exception as e:

        print("❌ erro envio telegram", e)