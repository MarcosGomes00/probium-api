import json
import requests
from datetime import datetime

# =========================
# TELEGRAM BOT 2
# =========================

BOT_TOKEN = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"
CHAT_ID = "-1003814625223"


# =========================
# ENVIAR MENSAGEM
# =========================

def send_message(msg):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


# =========================
# GERAR RELATÓRIO
# =========================

def generate_report():

    try:

        with open("bets_history.json") as f:
            bets = json.load(f)

    except:

        print("Nenhum histórico encontrado")
        return


    today = datetime.now().strftime("%Y-%m-%d")

    total = 0
    wins = 0
    losses = 0


    for bet in bets:

        if bet.get("date") != today:
            continue

        status = bet.get("status")

        if status == "TAKE":
            wins += 1
            total += 1

        elif status == "RED":
            losses += 1
            total += 1


    if total == 0:
        print("Nenhuma aposta finalizada hoje")
        return


    winrate = round((wins / total) * 100, 1)


    message = f"""
📊 *PROBIUM DAILY REPORT*

📅 {today}

━━━━━━━━━━━━

🎯 Apostas: {total}

✅ Take: {wins}  
❌ Red: {losses}

📈 Winrate: *{winrate}%*

━━━━━━━━━━━━

🤖 PROBIUM AI ENGINE
"""


    send_message(message)


# =========================
# EXECUTAR
# =========================

if __name__ == "__main__":

    generate_report()