
import random
from datetime import datetime
from services.database import db
from models.analysis import Analysis
from services.match_service import MatchService

class AnalysisGenerator:

    def generate_daily(self):

        matches = MatchService().get_today_matches()

        analyses = []

        for m in matches:

            probability = random.randint(70,90)

            confidence = "alta" if probability > 82 else "media"

            a = Analysis(
                home_team=m["home_team"],
                away_team=m["away_team"],
                league=m["league"],
                match_date=datetime.now(),
                market="casa_vence",
                odds=m["odds"],
                probability_ai=probability,
                confidence=confidence
            )

            db.session.add(a)
            analyses.append(a)

        db.session.commit()

        return analyses
