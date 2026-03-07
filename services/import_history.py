import requests
from flask import Flask
from config import Config
from services.database import db
from sqlalchemy import text


API_KEY = "a1b4dc55ed3248a09e8b8582e4dbc0c9"


LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1"
}


def fetch_matches(league):

    url = f"https://v3.football.api-sports.io/fixtures?league={league}&season=2024"

    headers = {
        "x-apisports-key": API_KEY
    }

    r = requests.get(url, headers=headers)

    return r.json()["response"]


def save_match(m):

    db.session.execute(text("""

    INSERT INTO matches_history
    (league, season, date, home_team, away_team, home_goals, away_goals)

    VALUES
    (:league,:season,:date,:home,:away,:hg,:ag)

    """), {

        "league": m["league"]["name"],
        "season": m["league"]["season"],
        "date": m["fixture"]["date"],
        "home": m["teams"]["home"]["name"],
        "away": m["teams"]["away"]["name"],
        "hg": m["goals"]["home"],
        "ag": m["goals"]["away"]

    })

    db.session.commit()


def run_import():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():

        for league in LEAGUES:

            print("Importando:", LEAGUES[league])

            matches = fetch_matches(league)

            for m in matches:

                if m["fixture"]["status"]["short"] == "FT":

                    save_match(m)

    print("Histórico importado")


if __name__ == "__main__":
    run_import()