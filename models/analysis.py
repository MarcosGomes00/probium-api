
from datetime import datetime
from services.database import db

class Analysis(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    home_team = db.Column(db.String(100))
    away_team = db.Column(db.String(100))
    league = db.Column(db.String(100))

    match_date = db.Column(db.DateTime)

    market = db.Column(db.String(50))
    odds = db.Column(db.Float)

    probability_ai = db.Column(db.Float)
    confidence = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
