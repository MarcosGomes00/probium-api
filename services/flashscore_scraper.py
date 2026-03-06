import requests

URL = "https://d.flashscore.com/x/feed/f_1_0_2_en_1"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Fsign": "SW9D1eZo"
}


def get_today_matches():

    r = requests.get(URL, headers=HEADERS)

    data = r.text.split("\n")

    matches = []

    for row in data:

        if not row.startswith("AA"):
            continue

        parts = row.split("¬")

        try:

            home = parts[2].split("÷")[1]
            away = parts[3].split("÷")[1]

            matches.append({
                "home": home,
                "away": away,
                "league": "Unknown",
                "country": "Unknown",
                "kickoff": ""
            })

        except:
            continue

    return matches