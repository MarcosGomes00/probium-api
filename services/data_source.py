import requests
from config import Config


LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_brazil_campeonato"
]


def get_matches_by_date(date):

    matches = []

    for league in LEAGUES:

        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"

        params = {
            "apiKey": Config.ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "dateFormat": "iso"
        }

        try:

            r = requests.get(url, params=params, timeout=10)

            if r.status_code != 200:
                print("Erro:", league, r.status_code)
                continue

            data = r.json()

            for game in data:

                commence = game.get("commence_time", "")

                if date not in commence:
                    continue

                matches.append({
                    "home": game["home_team"],
                    "away": game["away_team"],
                    "league": league,
                    "kickoff": commence
                })

        except Exception as e:

            print("Erro coletando jogos:", e)

    print(f"⚽ {len(matches)} jogos encontrados para {date}")

    return matches