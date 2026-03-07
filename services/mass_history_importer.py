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


SEASONS = [
    2024,
    2023,
    2022,
    2021,
    2020,
    2019,
    2018,
    2017,
    2016,
    2015
]


def fetch_matches(league_code, season):

    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?season={season}"

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


def collect_mass_history():

    print("🚀 Iniciando importação massiva de histórico")

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():

        for league_code in LEAGUES:

            print("🔎 Liga:", LEAGUES[league_code])

            for season in SEASONS:

                print("📅 Temporada:", season)

                matches = fetch_matches(league_code, season)

                for match in matches:

                    if match["status"] == "FINISHED":

                        save_match(match)

    print("✅ Importação finalizada")


if __name__ == "__main__":
    collect_mass_history()