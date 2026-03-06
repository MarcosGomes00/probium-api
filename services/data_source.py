import requests
from datetime import datetime
from config import Config


API_KEY = Config.API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}


# principais ligas
LEAGUES = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61    # Ligue 1
]


def get_matches_today():

    today = datetime.now().strftime("%Y-%m-%d")

    season = datetime.now().year  # temporada automática

    matches = []

    for league in LEAGUES:

        url = f"{BASE_URL}/fixtures"

        params = {
            "date": today,
            "league": league,
            "season": season
        }

        try:

            r = requests.get(url, headers=headers, params=params, timeout=10)

            data = r.json()

            fixtures = data.get("response", [])

            for f in fixtures:

                matches.append({
                    "home": f["teams"]["home"]["name"],
                    "away": f["teams"]["away"]["name"],
                    "home_id": f["teams"]["home"]["id"],
                    "away_id": f["teams"]["away"]["id"],
                    "league": f["league"]["name"],
                    "time": f["fixture"]["date"]
                })

        except Exception as e:

            print("Erro API football:", e)


    # fallback se não tiver jogos hoje
    if not matches:

        print("⚠ Nenhum jogo hoje — buscando próximos jogos")

        url = f"{BASE_URL}/fixtures"

        params = {
            "next": 20
        }

        r = requests.get(url, headers=headers, params=params, timeout=10)

        data = r.json()

        fixtures = data.get("response", [])

        for f in fixtures:

            matches.append({
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "home_id": f["teams"]["home"]["id"],
                "away_id": f["teams"]["away"]["id"],
                "league": f["league"]["name"],
                "time": f["fixture"]["date"]
            })

    return matches