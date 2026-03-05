import requests
import time
from services.predictor import predict_match
from services.telegram_bot import send_message

API_URL = "https://api.football-data.org/v4/matches"
API_TOKEN = "COLE_SUA_API_AQUI"

headers = {
    "X-Auth-Token": API_TOKEN
}

def scan_matches():

    response = requests.get(API_URL, headers=headers)

    if response.status_code != 200:
        print("Erro ao buscar jogos")
        return

    data = response.json()

    for match in data["matches"]:

        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]

        result = predict_match(home, away)

        home_prob = result["probabilities"]["home_win"]["prob"]
        away_prob = result["probabilities"]["away_win"]["prob"]

        if home_prob > 0.60:

            msg = f"""
⚽ JOGO ANALISADO

🏠 {home} vs {away}

📊 Probabilidade casa
{result['probabilities']['home_win']['bar']} {home_prob}

🔥 Sinal forte para vitória do mandante
"""

            send_message(msg)

        if away_prob > 0.60:

            msg = f"""
⚽ JOGO ANALISADO

🏠 {home} vs {away}

📊 Probabilidade visitante
{result['probabilities']['away_win']['bar']} {away_prob}

🔥 Sinal forte para vitória visitante
"""

            send_message(msg)


def start_scanner():

    while True:

        print("🔎 Escaneando jogos...")

        scan_matches()

        time.sleep(600)