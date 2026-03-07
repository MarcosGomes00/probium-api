import requests
from datetime import datetime
from config import Config


# ================================
# API FOOTBALL
# ================================

def get_api_football_games():

    url = "https://v3.football.api-sports.io/fixtures"

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    today = datetime.now().strftime("%Y-%m-%d")

    params = {
        "date": today
    }

    games = []

    try:

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        for g in data.get("response", []):

            games.append({
                "home": g["teams"]["home"]["name"],
                "away": g["teams"]["away"]["name"],
                "league": g["league"]["name"],
                "time": g["fixture"]["date"]
            })

    except Exception as e:

        print("API Football erro:", e)

    return games


# ================================
# ODDS API
# ================================

def get_odds_api_games():

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    params = {
        "apiKey": Config.ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h"
    }

    games = []

    try:

        r = requests.get(url, params=params, timeout=10)

        data = r.json()

        for g in data:

            games.append({
                "home": g["home_team"],
                "away": [t for t in g["teams"] if t != g["home_team"]][0],
                "league": "Premier League",
                "time": g["commence_time"]
            })

    except Exception as e:

        print("Odds API erro:", e)

    return games


# ================================
# SOFASCORE
# ================================

def get_sofascore_games():

    url = "https://api.sofascore.com/api/v1/sport/football/scheduled-events"

    games = []

    try:

        r = requests.get(url, timeout=10)

        data = r.json()

        for g in data.get("events", []):

            games.append({
                "home": g["homeTeam"]["name"],
                "away": g["awayTeam"]["name"],
                "league": g["tournament"]["name"],
                "time": g["startTimestamp"]
            })

    except Exception as e:

        print("SofaScore erro:", e)

    return games


# ================================
# AGREGADOR
# ================================

def get_all_games():

    games = []

    games += get_api_football_games()
    games += get_odds_api_games()
    games += get_sofascore_games()

    # remover duplicados
    unique = {}

    for g in games:

        key = f"{g['home']} vs {g['away']}"

        unique[key] = g

    games = list(unique.values())

    print(f"🌍 Total de jogos encontrados: {len(games)}")

    return games