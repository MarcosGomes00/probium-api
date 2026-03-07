import requests
from flask import Flask
from sqlalchemy import text

from config import Config
from services.database import db


API_KEY = "a1b4dc55ed3248a09e8b8582e4dbc0c9"

LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1"
}


def fetch_matches(league_code):

    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches"

    headers = {
        "X-Auth-Token": API_KEY
    }

    r = requests.get(url, headers=headers, timeout=15)

    data = r.json()

    return data.get("matches", [])


def save_match(match):

    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]

    goals_home = match["score"]["fullTime"]["home"]
    goals_away = match["score"]["fullTime"]["away"]

    if goals_home is None:
        return

    record = {
        "league": match["competition"]["name"],
        "season": match["season"]["startDate"][:4],
        "date": match["utcDate"],
        "home_team": home,
        "away_team": away,
        "home_goals": goals_home,
        "away_goals": goals_away
    }

    db.session.execute(
        text("""
        INSERT INTO matches_history
        (league, season, date, home_team, away_team, home_goals, away_goals)
        VALUES (:league, :season, :date, :home_team, :away_team, :home_goals, :away_goals)
        """),
        record
    )

    db.session.commit()


def collect_history():

    print("📥 Baixando histórico das ligas...")

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():

        for code in LEAGUES:

            print("🔎 Liga:", LEAGUES[code])

            matches = fetch_matches(code)

            for match in matches:

                if match["status"] == "FINISHED":

                    save_match(match)

    print("✅ Histórico importado.")


if __name__ == "__main__":
    collect_history()