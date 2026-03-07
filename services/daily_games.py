import requests
from config import Config
from services.poisson_model import over25_prob
from services.telegram_bot import send_bet_message

API_URL = "https://v3.football.api-sports.io/fixtures"


def get_today_games():

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    params = {
        "date": "2026-03-07"
    }

    r = requests.get(API_URL, headers=headers, params=params)

    data = r.json()

    games = []

    for g in data["response"]:

        games.append({
            "league": g["league"]["name"],
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "time": g["fixture"]["date"]
        })

    return games


def analyze_games():

    games = get_today_games()

    print("⚽ Jogos encontrados:", len(games))

    for g in games:

        prob = over25_prob(1.6, 1.3)

        if prob < 0.65:
            continue

        bet = {
            "league": g["league"],
            "home": g["home"],
            "away": g["away"],
            "prob": prob,
            "market": "Over 2.5"
        }

        send_bet_message(bet)

        print("📩 enviado:", g["home"], "x", g["away"])


if __name__ == "__main__":

    analyze_games()