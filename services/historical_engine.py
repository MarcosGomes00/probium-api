import requests
from config import Config


API_KEY = Config.API_FOOTBALL_KEY
BASE_URL = "https://v3.football.api-sports.io"


headers = {
    "x-apisports-key": API_KEY
}


class HistoricalEngine:

    def last_matches(self, team_id):

        url = f"{BASE_URL}/fixtures"

        params = {
            "team": team_id,
            "last": 5
        }

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        matches = data.get("response", [])

        goals_for = 0
        goals_against = 0
        wins = 0

        for m in matches:

            home = m["teams"]["home"]["id"]
            goals_home = m["goals"]["home"]
            goals_away = m["goals"]["away"]

            if home == team_id:

                goals_for += goals_home
                goals_against += goals_away

                if goals_home > goals_away:
                    wins += 1

            else:

                goals_for += goals_away
                goals_against += goals_home

                if goals_away > goals_home:
                    wins += 1

        return {
            "form": wins / 5,
            "goals_for": goals_for / 5,
            "goals_against": goals_against / 5
        }