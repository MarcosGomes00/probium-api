import os
import requests

from services.auto_analyzer import analyze_today_matches


BOT_TOKEN = os.getenv("BOT1_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")


def send_daily_predictions():

    predictions = analyze_today_matches()

    for game in predictions:

        message = f"""

⚽ PROBIUM AI

{game['match']}

📊 xG
🏠 {game['expected_goals']['home']}
✈️ {game['expected_goals']['away']}

📈 Probabilidades

🏠 Casa: {game['probabilities']['home_win']['prob']}
🤝 Empate: {game['probabilities']['draw']['prob']}
✈️ Fora: {game['probabilities']['away_win']['prob']}

📊 Over 2.5
🔥 {game['over_under_2_5']['over']}

"""

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        requests.post(

            url,

            json={
                "chat_id": GROUP_ID,
                "text": message
            }

        )