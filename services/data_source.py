import requests
from bs4 import BeautifulSoup
from config import Config


# ---------------------------
# 1️⃣ ODDS API
# ---------------------------

def odds_api_matches():

    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"

    params = {
        "apiKey": Config.ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h"
    }

    matches = []

    try:

        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            return []

        data = r.json()

        for game in data:

            home = game["home_team"]

            away = [t for t in game["teams"] if t != home][0]

            matches.append({
                "home": home,
                "away": away,
                "league": game["sport_title"]
            })

    except Exception as e:

        print("OddsAPI erro:", e)

    return matches


# ---------------------------
# 2️⃣ API FOOTBALL
# ---------------------------

def api_football_matches():

    url = "https://v3.football.api-sports.io/fixtures"

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    matches = []

    try:

        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            return []

        data = r.json()

        for game in data.get("response", []):

            matches.append({
                "home": game["teams"]["home"]["name"],
                "away": game["teams"]["away"]["name"],
                "league": game["league"]["name"]
            })

    except Exception as e:

        print("API Football erro:", e)

    return matches


# ---------------------------
# 3️⃣ SCOREBAT (API pública)
# ---------------------------

def scorebat_matches():

    url = "https://www.scorebat.com/video-api/v3/"

    matches = []

    try:

        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            return []

        data = r.json()

        for game in data.get("response", []):

            title = game["title"]

            if " vs " not in title:
                continue

            home, away = title.split(" vs ")

            matches.append({
                "home": home,
                "away": away,
                "league": game["competition"]
            })

    except Exception as e:

        print("Scorebat erro:", e)

    return matches


# ---------------------------
# 4️⃣ SOCCERWAY
# ---------------------------

def soccerway_matches():

    url = "https://int.soccerway.com/matches/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    matches = []

    try:

        r = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        games = soup.select("td.team-a")

        for g in games[:30]:

            home = g.text.strip()

            away_tag = g.find_next("td", class_="team-b")

            if not away_tag:
                continue

            away = away_tag.text.strip()

            matches.append({
                "home": home,
                "away": away,
                "league": "Soccerway"
            })

    except Exception as e:

        print("Soccerway erro:", e)

    return matches


# ---------------------------
# COLETOR PRINCIPAL
# ---------------------------

def get_matches_today():

    print("🔎 Buscando jogos (OddsAPI)...")
    matches = odds_api_matches()

    if matches:
        print(f"⚽ {len(matches)} jogos via OddsAPI")
        return matches


    print("🔎 Buscando jogos (API Football)...")
    matches = api_football_matches()

    if matches:
        print(f"⚽ {len(matches)} jogos via API Football")
        return matches


    print("🔎 Buscando jogos (Scorebat)...")
    matches = scorebat_matches()

    if matches:
        print(f"⚽ {len(matches)} jogos via Scorebat")
        return matches


    print("🔎 Buscando jogos (Soccerway)...")
    matches = soccerway_matches()

    print(f"⚽ {len(matches)} jogos via Soccerway")

    return matches