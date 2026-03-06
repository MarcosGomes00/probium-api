import requests
from services.database import db
from models.match import Match

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"


def import_matches():

    print("⬇ Importando partidas...")

    response = requests.get(URL)

    if response.status_code != 200:
        print("Erro ao acessar dados")
        return

    data = response.json()

    for event in data.get("events", []):

        competitors = event["competitions"][0]["competitors"]

        home = None
        away = None
        home_goals = None
        away_goals = None

        for team in competitors:

            if team["homeAway"] == "home":
                home = team["team"]["displayName"]
                home_goals = team.get("score")

            if team["homeAway"] == "away":
                away = team["team"]["displayName"]
                away_goals = team.get("score")

        if home and away:

            match = Match(
                home_team=home,
                away_team=away,
                home_goals=home_goals,
                away_goals=away_goals
            )

            db.session.add(match)

    db.session.commit()

    print("✔ Partidas salvas no banco")