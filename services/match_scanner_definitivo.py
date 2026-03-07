import requests
from datetime import datetime
from config import Config

API_URL = "https://v3.football.api-sports.io/fixtures"


# Regras de stake baseadas na tabela que estava no arquivo
STAKE_RULES = {
    "CERTO": {
        "prob_min": 0.90,
        "stake": 1.5
    },
    "FORTE": {
        "prob_min": 0.80,
        "stake": 1.0
    },
    "BOM": {
        "prob_min": 0.65,
        "stake": 0.75
    }
}


def get_matches():

    print("🔎 PROBIUM analisando jogos...")

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    params = {
        "next": 50
    }

    response = requests.get(API_URL, headers=headers, params=params)

    data = response.json()

    matches = []

    for game in data.get("response", []):

        home = game["teams"]["home"]["name"]
        away = game["teams"]["away"]["name"]

        league = game["league"]["name"]

        kickoff = game["fixture"]["date"]

        matches.append({
            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff
        })

    print(f"⚽ {len(matches)} jogos encontrados")

    return matches