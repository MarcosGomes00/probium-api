import requests
from config import Config
from services.telegram_bot import send_bet_message
from services.poisson_model import over25_prob
from datetime import datetime

ODDS_API_KEY = "6a1c0078b3ed09b42fbacee8f07e7cc3"


def get_today_games():

    today = datetime.utcnow().date()

    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "totals",
        "dateFormat": "iso"
    }

    r = requests.get(url, params=params)

    if r.status_code != 200:
        print("Erro ao buscar jogos")
        return []

    return r.json()


def extract_odds(match):

    bookmakers = match.get("bookmakers", [])

    for book in bookmakers:

        markets = book.get("markets", [])

        for market in markets:

            if market["key"] == "totals":

                outcomes = market["outcomes"]

                for o in outcomes:

                    if o["name"] == "Over" and o["point"] == 2.5:

                        return o["price"]

    return None


def analyze_games():

    games = get_today_games()

    for g in games:

        home = g["home_team"]
        away = g["away_team"]
        league = g["sport_title"]

        kickoff = g["commence_time"][11:16]

        odd = extract_odds(g)

        if odd is None:
            continue

        prob = over25_prob(home, away)

        ev = round((prob * odd) - 1, 2)

        if prob > 0.6 and ev > 0:

            bet = {

                "home": home,
                "away": away,
                "league": league,
                "kickoff": kickoff,
                "market": "Over 2.5 Goals",
                "prob": round(prob * 100, 1),
                "odd": odd,
                "ev": ev

            }

            send_bet_message(bet)

            print("Enviado:", home, "x", away)


if __name__ == "__main__":

    analyze_games()