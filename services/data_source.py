import requests
from datetime import datetime
from config import Config


API_KEY = Config.API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": API_KEY
}


LEAGUES = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    71,   # Brasileirão
    94,   # Copa do Brasil
    2,    # Champions League
    13    # Libertadores
]


def fetch_api_football():

    matches = []

    today = datetime.now().strftime("%Y-%m-%d")
    season = datetime.now().year

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
                    "league_id": f["league"]["id"],
                    "time": f["fixture"]["date"]

                })

        except Exception as e:

            print("Erro API Football:", e)

    return matches


def fetch_next_matches():

    matches = []

    url = f"{BASE_URL}/fixtures"

    params = {
        "next": 100
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
                "league_id": f["league"]["id"],
                "time": f["fixture"]["date"]

            })

    except Exception as e:

        print("Erro próximos jogos:", e)

    return matches


def get_matches_today():

    matches = fetch_api_football()

    if not matches:

        print("⚠ Nenhum jogo hoje — buscando próximos")

        matches = fetch_next_matches()

    return matches