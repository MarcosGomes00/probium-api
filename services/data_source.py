import requests
from bs4 import BeautifulSoup

URL = "https://www.flashscore.com/football/"

def get_matches_today():

    matches = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(URL, headers=headers)

        soup = BeautifulSoup(response.text, "html.parser")

        games = soup.select(".event__match")

        for game in games[:30]:

            try:

                home = game.select_one(".event__participant--home").text.strip()
                away = game.select_one(".event__participant--away").text.strip()

                matches.append({
                    "home": home,
                    "away": away,
                    "league": "Football"
                })

            except:
                continue

    except Exception as e:

        print("❌ Erro ao buscar jogos:", e)

    print(f"⚽ {len(matches)} jogos encontrados")

    return matches