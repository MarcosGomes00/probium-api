import requests
from datetime import datetime
from config import Config


BASE_URL = "https://v3.football.api-sports.io/fixtures"

HEADERS = {
    "x-apisports-key": Config.API_FOOTBALL_KEY
}


def get_matches_today():

    matches = []

    # primeiro tenta jogos do dia
    today = datetime.now().strftime("%Y-%m-%d")

    params = {
        "date": today
    }

    try:

        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)

        data = r.json()

        fixtures = data.get("response", [])

        for f in fixtures:

            matches.append({
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "league": f["league"]["name"],
                "time": f["fixture"]["date"]
            })

    except Exception as e:

        print("Erro API Football:", e)

    # fallback → pega próximos jogos
    if not matches:

        print("⚠ Nenhum jogo hoje — buscando próximos")

        params = {
            "next": 20
        }

        try:

            r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)

            data = r.json()

            fixtures = data.get("response", [])

            for f in fixtures:

                matches.append({
                    "home": f["teams"]["home"]["name"],
                    "away": f["teams"]["away"]["name"],
                    "league": f["league"]["name"],
                    "time": f["fixture"]["date"]
                })

        except Exception as e:

            print("Erro API Football:", e)

    print(f"⚽ {len(matches)} jogos encontrados")

    return matches