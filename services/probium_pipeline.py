import json
import random
from datetime import datetime

from services.data_source import get_matches_today
from services.odds_collector import get_odds
from services.poisson_model import over25_prob
from services.telegram_bot import send_bet_message


HISTORY_FILE = "bets_history.json"


def load_history():

    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_history(data):

    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def run_pipeline():

    print("🔎 PROBIUM analisando jogos...")

    matches = get_matches_today()
    odds = get_odds()

    history = load_history()

    bets = []

    for match in matches:

        home = match["home"]
        away = match["away"]

        odd_data = next((o for o in odds if o["home"] == home and o["away"] == away), None)

        if not odd_data:
            continue

        odd = odd_data["odd"]

        home_attack = random.uniform(1.2, 2.2)
        away_attack = random.uniform(1.0, 2.0)

        prob = over25_prob(home_attack, away_attack)

        ev = (prob * odd) - 1

        if ev > 0.05:

            bet = {
                "date": datetime.utcnow().isoformat(),
                "home": home,
                "away": away,
                "market": "over_2.5",
                "odd": odd,
                "probability": round(prob, 2),
                "ev": round(ev, 3),
                "status": "pending"
            }

            history.append(bet)
            bets.append(bet)

    save_history(history)

    if not bets:

        print("⚠ nenhuma aposta encontrada")
        return

    for bet in bets[:3]:

        message = f"""
🤖 PROBIUM AI

⚽ {bet['home']} vs {bet['away']}

🎯 Entrada: Over 2.5

📊 Probabilidade: {bet['probability']*100:.1f}%
💰 Odd: {bet['odd']}
📈 EV: {bet['ev']}
"""

        send_bet_message(message)

        print("✅ aposta enviada:", bet["home"], "vs", bet["away"])