import requests
from rapidfuzz import fuzz

API_KEY = "6a1c0078b3ed09b42fbacee8f07e7cc3"

SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_brazil_campeonato",
    "soccer_usa_mls",
    "soccer_portugal_primeira_liga",
    "soccer_netherlands_eredivisie"
]

odds_cache = []


def normalize(name):
    return (
        name.lower()
        .replace("fc", "")
        .replace(".", "")
        .replace("-", " ")
        .replace("cf", "")
        .replace("club", "")
        .strip()
    )


def load_odds():

    global odds_cache
    odds_cache = []

    for sport in SPORTS:

        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"

        params = {
            "apiKey": API_KEY,
            "regions": "eu",
            "markets": "h2h"
        }

        try:

            response = requests.get(url, params=params)

            if response.status_code != 200:
                continue

            data = response.json()

            odds_cache.extend(data)

        except:
            continue

    print(f"📊 Odds carregadas: {len(odds_cache)} jogos")


def get_odds(home, away):

    home = normalize(home)
    away = normalize(away)

    for match in odds_cache:

        home_team = normalize(match["home_team"])
        away_team = normalize(match["away_team"])

        home_score = fuzz.ratio(home, home_team)
        away_score = fuzz.ratio(away, away_team)

        if home_score > 60 and away_score > 60:

            bookmakers = match.get("bookmakers")

            if not bookmakers:
                return None

            markets = bookmakers[0].get("markets")

            if not markets:
                return None

            outcomes = markets[0].get("outcomes")

            odds = {}

            for outcome in outcomes:

                name = normalize(outcome["name"])

                if fuzz.ratio(name, home_team) > 60:
                    odds["home_win"] = outcome["price"]

                elif fuzz.ratio(name, away_team) > 60:
                    odds["away_win"] = outcome["price"]

                else:
                    odds["draw"] = outcome["price"]

            return odds

    return None