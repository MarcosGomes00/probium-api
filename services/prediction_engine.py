from flask import Flask
from config import Config
from services.database import db
from sqlalchemy import text


def predict_match(home, away):

    stats = db.session.execute(text("""

    SELECT
    AVG(home_goals) as home_avg,
    AVG(away_goals) as away_avg

    FROM matches_history

    WHERE home_team = :home
    OR away_team = :away

    """), {

        "home": home,
        "away": away

    }).fetchone()

    if stats.home_avg is None:
        return None

    prob = ((stats.home_avg + stats.away_avg) / 2) * 50

    return round(prob,2)