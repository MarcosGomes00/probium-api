import requests

# =========================
# CONFIG TELEGRAM
# =========================

BOT_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"


# =========================
# ENVIAR MENSAGEM
# =========================

def send_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


# =========================
# MENSAGEM PREMIUM COMPACTA
# =========================

def send_bet_message(bet):

    home = bet.get("home")
    away = bet.get("away")
    league = bet.get("league", "Liga")
    kickoff = bet.get("kickoff", "--:--")
    market = bet.get("market")
    prob = bet.get("prob")
    odd = bet.get("odd")

    message = (
        f"📊 *PROBIUM AI*\n\n"
        f"🏆 {league}\n"
        f"⚽ {home} vs {away}\n"
        f"⏰ {kickoff}\n\n"
        f"🎯 *{market}*\n"
        f"📈 Prob: *{prob}%* | 📉 Odd: *{odd}*"
    )

    send_message(message)


def init_bot():
    print("🤖 Telegram bot initialized")