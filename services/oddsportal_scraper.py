import requests
from bs4 import BeautifulSoup


URL = "https://www.oddsportal.com/matches/soccer/"


def get_odds():

    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})

    soup = BeautifulSoup(r.text, "html.parser")

    games = []

    rows = soup.select("table tbody tr")

    for row in rows:

        cols = row.find_all("td")

        if len(cols) < 3:
            continue

        try:

            teams = cols[1].text.split(" - ")

            home = teams[0]
            away = teams[1]

            odd = float(cols[-1].text)

            games.append({
                "home": home,
                "away": away,
                "odd": odd
            })

        except:
            continue

    return games
