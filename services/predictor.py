from services.database import db
from sqlalchemy import text


def predict_match(home, away):

    try:

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

        # se não encontrar dados
        if not stats:
            return {
                "home": home,
                "away": away,
                "prediction": "no data",
                "probability": 0
            }

        home_avg = stats.home_avg
        away_avg = stats.away_avg

        if home_avg is None or away_avg is None:
            return {
                "home": home,
                "away": away,
                "prediction": "insufficient data",
                "probability": 0
            }

        probability = ((home_avg + away_avg) / 2) * 50

        return {
            "home": home,
            "away": away,
            "prediction": "Over 2.5",
            "probability": round(probability, 2)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }