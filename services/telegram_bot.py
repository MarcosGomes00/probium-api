import requests

# =========================
# CONFIGURAÇÃO TELEGRAM
# =========================

BOT_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"


# =========================
# INICIAR BOT
# =========================

def init_bot():
    print("🤖 Telegram bot initialized")


# =========================
# ENVIAR MENSAGEM SIMPLES
# =========================

def send_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:

        requests.post(url, json=payload, timeout=10)

    except Exception as e:

        print("Telegram error:", e)


# =========================
# FUNÇÃO USADA PELO PIPELINE
# =========================

def send_bet_message(bet):

    message = "🎯 APOSTA DETECTADA\n\n"

    message += f"Jogo: {bet.get('home')} x {bet.get('away')}\n"
    message += f"Mercado: {bet.get('market')}\n"
    message += f"Probabilidade: {bet.get('prob')}%\n"
    message += f"Odd: {bet.get('odd')}\n"
    message += f"EV: {bet.get('ev')}\n"

    send_message(message)