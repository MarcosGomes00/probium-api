import requests
from config import Config

API_KEY = Config.API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}


def get_team_stats(team_id, league_id):

    url = f"{BASE_URL}/teams/statistics"

    params = {
        "season": 2025,
        "league": league_id,
        "team": team_id
    }

    try:

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        if not data["response"]:
            return None

        stats = data["response"]

        games = stats["fixtures"]["played"]["total"]

        goals_for = stats["goals"]["for"]["total"]["total"]
        goals_against = stats["goals"]["against"]["total"]["total"]

        if games == 0:
            return None

        attack = goals_for / games
        defense = goals_against / games

        return attack, defense

    except Exception as e:

        print("Erro stats:", e)

        return None