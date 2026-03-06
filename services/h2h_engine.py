import requests
from config import Config


API_KEY = Config.API_FOOTBALL_KEY
BASE_URL = "https://v3.football.api-sports.io"


headers = {
    "x-apisports-key": API_KEY
}


class H2HEngine:

    def get_h2h(self, team_a, team_b):

        url = f"{BASE_URL}/fixtures/headtohead"

        params = {
            "h2h": f"{team_a}-{team_b}",
            "last": 5
        }

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        matches = data.get("response", [])

        goals = 0

        for m in matches:

            goals += m["goals"]["home"]
            goals += m["goals"]["away"]

        if matches:

            avg_goals = goals / len(matches)

        else:

            avg_goals = 2.5

        return avg_goals