from services.database import db

class MatchHistory(db.Model):

    __tablename__ = "matches_history"

    id = db.Column(db.Integer, primary_key=True)

    league = db.Column(db.String(100))
    season = db.Column(db.String(20))
    date = db.Column(db.String(50))

    home_team = db.Column(db.String(100))
    away_team = db.Column(db.String(100))

    home_goals = db.Column(db.Integer)
    away_goals = db.Column(db.Integer)