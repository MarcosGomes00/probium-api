from flask import Flask
from config import Config
from services.database import db
from services.prediction_engine import predict_match
from sqlalchemy import text


def generate_ticket():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    picks = []

    with app.app_context():

        matches = db.session.execute(text("""

        SELECT home_team, away_team

        FROM daily_matches

        """))

        for m in matches:

            prob = predict_match(m.home_team, m.away_team)

            if prob and prob > 65:

                picks.append({
                    "home": m.home_team,
                    "away": m.away_team,
                    "prob": prob
                })

    return picks