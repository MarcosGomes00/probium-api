import requests
from datetime import datetime
from flask import Flask
from config import Config
from services.database import db
from sqlalchemy import text


def fetch_matches():

    today = datetime.utcnow().strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={today}"

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    r = requests.get(url, headers=headers)

    data = r.json()

    return data.get("response", [])


def save_matches(matches):

    for m in matches:

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        date = m["fixture"]["date"]

        db.session.execute(text("""

        INSERT INTO daily_matches
        (home_team, away_team, match_date)

        VALUES (:home,:away,:date)

        """), {

            "home": home,
            "away": away,
            "date": date

        })

    db.session.commit()


def collect_today_matches():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():

        matches = fetch_matches()

        save_matches(matches)

        print("Jogos do dia coletados")


if __name__ == "__main__":
    collect_today_matches()