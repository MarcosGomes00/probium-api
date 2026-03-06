import json
from services.telegram_bot import send_report_message


HISTORY_FILE = "bets_history.json"


def send_daily_report():

    try:
        with open(HISTORY_FILE, "r") as f:
            bets = json.load(f)
    except:
        bets = []

    total = len(bets)

    greens = len([b for b in bets if b.get("result") == "GREEN"])
    reds = len([b for b in bets if b.get("result") == "RED"])

    winrate = 0

    if total > 0:
        winrate = (greens / total) * 100

    message = f"""
📊 RELATÓRIO PROBIUM

Total apostas: {total}

Greens: {greens}
Reds: {reds}

Winrate: {winrate:.1f}%
"""

    send_report_message(message)