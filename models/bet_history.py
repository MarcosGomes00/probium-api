from services.database import db
from datetime import datetime


class BetHistory(db.Model):

    __tablename__ = "bets_history"

    id = db.Column(db.Integer, primary_key=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    home = db.Column(db.String(100))
    away = db.Column(db.String(100))

    league = db.Column(db.String(100))

    market = db.Column(db.String(50))

    odd = db.Column(db.Float)

    probability = db.Column(db.Float)

    ev = db.Column(db.Float)

    result = db.Column(db.String(20), default="pending")