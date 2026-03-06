import requests
from datetime import datetime


API_KEY = "a1b4dc55ed3248a09e8b8582e4dbc0c9"
BASE_URL = "https://api.football-data.org/v4/matches"


def get_matches():

    headers = {
        "X-Auth-Token": API_KEY
    }

    try:

        r = requests.get(BASE_URL, headers=headers)

        data = r.json()

    except:

        return []


    matches = []

    for m in data.get("matches", []):

        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]

        league = m["competition"]["name"]

        kickoff = m["utcDate"]

        matches.append({

            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff,

            "elo_home": 1700,
            "elo_away": 1700

        })

    return matches