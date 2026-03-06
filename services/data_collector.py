import requests

LEAGUES = [

    "eng.1",
    "esp.1",
    "ger.1",
    "ita.1",
    "fra.1",

    "por.1",
    "ned.1",
    "bel.1",
    "tur.1",

    "bra.1",
    "arg.1",

    "usa.1",

    "jpn.1",
    "kor.1",

    "mex.1"
]


def get_today_matches():

    matches = []

    for league in LEAGUES:

        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

        try:

            response = requests.get(url)

            if response.status_code != 200:
                continue

            data = response.json()

            for event in data.get("events", []):

                status = event["status"]["type"]["state"]

                if status != "pre":
                    continue

                competitors = event["competitions"][0]["competitors"]

                home = None
                away = None

                for team in competitors:

                    if team["homeAway"] == "home":
                        home = team["team"]["displayName"]

                    if team["homeAway"] == "away":
                        away = team["team"]["displayName"]

                if home and away:

                    matches.append({
                        "home": home,
                        "away": away
                    })

        except:
            continue

    print(f"⚽ Jogos futuros encontrados: {len(matches)}")

    return matches