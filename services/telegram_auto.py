import os
import requests

from services.auto_analyzer import analyze_today_matches


BOT_TOKEN = os.getenv("BOT1_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_GROUP_ID")


def send_value_alerts():

    games = analyze_today_matches()

    for game in games:

        ev_home = game["value_bet"]["home_ev"]
        ev_draw = game["value_bet"]["draw_ev"]
        ev_away = game["value_bet"]["away_ev"]

        # envia alerta apenas se EV positivo

        if ev_home > 0 or ev_draw > 0 or ev_away > 0:

            message = f"""

⚽ PROBIUM VALUE BET ALERT

{game['match']}

📊 xG
🏠 {game['expected_goals']['home']}
✈️ {game['expected_goals']['away']}

📈 Probabilidades
🏠 Casa {game['probabilities']['home_win']['prob']}
🤝 Empate {game['probabilities']['draw']['prob']}
✈️ Fora {game['probabilities']['away_win']['prob']}

💰 Value Bet

🏠 Casa EV {ev_home}
🤝 Empate EV {ev_draw}
✈️ Fora EV {ev_away}

"""

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

            requests.post(

                url,

                json={
                    "chat_id": CHAT_ID,
                    "text": message
                }

            )