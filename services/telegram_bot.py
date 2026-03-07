import requests

# =========================
# CONFIGURAÇÕES DO TELEGRAM
# =========================

BOT1_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
BOT2_TOKEN = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"

CHAT_ID = "-1003814625223"


# =========================
# INICIAR BOT
# =========================

def init_bot():
    print("🤖 Telegram bot initialized")


# =========================
# ENVIAR MENSAGEM
# =========================

def send_message(message):

    url = f"https://api.telegram.org/bot{BOT1_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:

        r = requests.post(url, json=payload, timeout=10)

        if r.status_code != 200:
            print("Telegram error:", r.text)

    except Exception as e:

        print("Telegram connection error:", e)


# =========================
# ENVIAR BILHETE
# =========================

def send_ticket(picks):

    message = "🎯 BILHETE PROBIUM AI\n\n"

    for p in picks:

        message += f"{p['home']} x {p['away']}\n"
        message += f"Probabilidade: {p['prob']}%\n\n"

    send_message(message)