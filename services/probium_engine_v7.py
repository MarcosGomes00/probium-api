import requests
import statistics
from config import Config

API_KEY = Config.API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}


def get_last_matches(team_id):

    url = f"{BASE_URL}/fixtures"

    params = {
        "team": team_id,
        "last": 5
    }

    try:

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        matches = data.get("response", [])

        goals = []

        for m in matches:

            home = m["goals"]["home"]
            away = m["goals"]["away"]

            if home is None or away is None:
                continue

            goals.append(home + away)

        if not goals:
            return 2.5

        return statistics.mean(goals)

    except:

        return 2.5


def analyze_match(match):

    home_id = match.get("home_id")
    away_id = match.get("away_id")

    home_avg = get_last_matches(home_id)
    away_avg = get_last_matches(away_id)

    # média de gols estimada
    expected_goals = (home_avg + away_avg) / 2

    over_score = min(expected_goals / 3.5, 1)

    btts_score = min(expected_goals / 4, 1)

    under_score = 1 - over_score

    markets = {

        "OVER 2.5": over_score,
        "BTTS SIM": btts_score,
        "UNDER 2.5": under_score

    }

    market = max(markets, key=markets.get)

    probability = markets[market]

    return market, probability