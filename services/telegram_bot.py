import requests

# =========================
# CONFIG TELEGRAM
# =========================

BOT_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"


# =========================
# ENVIAR MENSAGEM SIMPLES
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
# MENSAGEM PROFISSIONAL
# =========================

def send_bet_message(bet):

    home = bet.get("home")
    away = bet.get("away")
    market = bet.get("market")
    prob = bet.get("prob")
    odd = bet.get("odd")
    ev = bet.get("ev")
    league = bet.get("league", "Liga desconhecida")
    kickoff = bet.get("kickoff", "--:--")

    message = f"""
📊 *PROBIUM AI — ANÁLISE DE PARTIDA*

🏆 *{league}*

⚽ *{home} (Casa)*  
✈️ *{away} (Visitante)*

⏰ *Horário:* {kickoff}

━━━━━━━━━━━━━━━

📈 *Probabilidade:* {prob}%
📉 *Odd média:* {odd}
💰 *Value Bet:* {ev}

━━━━━━━━━━━━━━━

🎯 *Mercado recomendado*
➡️ {market}

━━━━━━━━━━━━━━━

🤖 *Análise gerada por*  
PROBIUM AI ENGINE
"""

    send_message(message)


# =========================
# INICIAR BOT
# =========================

def init_bot():
    print("🤖 Telegram bot initialized")